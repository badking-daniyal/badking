"""Regression tests for Session Storage hardening (PBKDF2 v3, fsync, locks).

Covers the 11 failure scenarios from the hardening mission. All inputs are
synthetic; no real credential or session is used. No previous test is removed
or weakened here.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from badking.hybrid import session as smod
from badking.hybrid.session import (
    MAGIC_V1,
    MAGIC_V2,
    MODE_AESGCM,
    MODE_AESGCM_V3,
    MODE_PLAIN,
    MODE_XOR_HMAC,
    PBKDF2_ROUNDS,
    PBKDF2_ROUNDS_V3,
    Session,
    SessionError,
    SessionStore,
    _derive_key,
    _xor_stream,
)

PW = "hardening-test-password-1234"


def make_legacy(path, password=PW):
    payload = json.dumps(
        {"version": 1, "sessions": {"user:1": {"access_token": "legacy", "user_id": 1}}}
    ).encode()
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    body = _xor_stream(payload, key)
    mac = hmac.new(key, body, hashlib.sha256).digest()
    path.write_bytes(MAGIC_V1 + MODE_XOR_HMAC + salt + mac + body)


def make_v2(path, password=PW):
    """A genuine legacy BKS2 file with 200k rounds (header 33 bytes)."""
    payload = json.dumps(
        {"version": 2, "sessions": {"user:1": {"access_token": "old-v2", "user_id": 1}}}
    ).encode()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(password, salt, PBKDF2_ROUNDS)
    header = MAGIC_V2 + MODE_AESGCM + salt + nonce
    path.write_bytes(header + AESGCM(key).encrypt(nonce, payload, header))


# --- PBKDF2 versioning ---

def test_pbkdf2_v3_rounds_and_header(tmp_path):
    assert PBKDF2_ROUNDS_V3 > PBKDF2_ROUNDS
    p = tmp_path / "s.session"
    SessionStore(p, password=PW).put(Session(user_id=1))
    blob = p.read_bytes()
    assert blob[:5] == MAGIC_V2 + MODE_AESGCM_V3
    rounds = int.from_bytes(blob[5:9], "big")
    assert rounds == PBKDF2_ROUNDS_V3


def test_legacy_v2_still_readable(tmp_path):
    """Old BKS2 files (200k, 33-byte header) must remain readable."""
    p = tmp_path / "old.session"
    make_v2(p)
    store = SessionStore(p, password=PW)
    assert store.format_version(p.read_bytes()) == "BKS2"
    assert store.get("user:1").access_token == "old-v2"


def test_migrate_v2_to_v3(tmp_path):
    p = tmp_path / "old.session"
    make_v2(p)
    original = p.read_bytes()
    store = SessionStore(p, password=PW)
    assert store.needs_migration() is True
    assert store.migrate_to_v2() is True
    assert store.format_version(p.read_bytes()) == "BKS3"
    assert store.get("user:1").access_token == "old-v2"
    assert (tmp_path / "old.session.bak").read_bytes() == original
    assert store.migrate_to_v2() is False  # idempotent


def test_rounds_in_header_is_authenticated(tmp_path):
    """Tampering with the rounds field must fail (AAD + KDF binding)."""
    p = tmp_path / "s.session"
    SessionStore(p, password=PW).put(Session(user_id=1))
    blob = bytearray(p.read_bytes())
    blob[8] ^= 0x01  # change rounds
    p.write_bytes(bytes(blob))
    with pytest.raises(SessionError):
        SessionStore(p, password=PW).load_all()


def test_absurd_rounds_rejected(tmp_path):
    p = tmp_path / "s.session"
    SessionStore(p, password=PW).put(Session(user_id=1))
    blob = bytearray(p.read_bytes())
    blob[5:9] = (99_999_999).to_bytes(4, "big")
    p.write_bytes(bytes(blob))
    with pytest.raises(SessionError):
        SessionStore(p, password=PW).load_all()


# --- atomic write / fsync ---

def test_fsync_called_on_save(tmp_path):
    p = tmp_path / "s.session"
    store = SessionStore(p, password=PW)
    with patch.object(smod.os, "fsync", wraps=os.fsync) as spy:
        store.put(Session(user_id=1))
    assert spy.call_count >= 1


def test_fsync_failure_keeps_original(tmp_path):
    p = tmp_path / "s.session"
    store = SessionStore(p, password=PW)
    store.put(Session(user_id=1, name="original"))
    original = p.read_bytes()
    real_fsync = os.fsync

    def fail_fsync(fd):
        raise OSError("simulated fsync failure")

    with patch.object(smod.os, "fsync", side_effect=fail_fsync):
        with pytest.raises(OSError):
            store.put(Session(user_id=2, name="new"))
    assert p.read_bytes() == original
    with patch.object(smod.os, "fsync", wraps=real_fsync):
        assert store.load_all()["user:1"].name == "original"


def test_crash_before_replace_keeps_original(tmp_path):
    p = tmp_path / "s.session"
    store = SessionStore(p, password=PW)
    store.put(Session(user_id=1, name="original"))
    original = p.read_bytes()
    with patch.object(smod.os, "replace", side_effect=OSError("crash before replace")):
        with pytest.raises(OSError):
            store.put(Session(user_id=2))
    assert p.read_bytes() == original


def test_crash_after_replace_leaves_valid_file(tmp_path):
    p = tmp_path / "s.session"
    store = SessionStore(p, password=PW)
    store.put(Session(user_id=1, name="original"))
    real_replace = os.replace
    calls = {"n": 0}

    def replace_then_fail(a, b):
        real_replace(a, b)
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("crash after replace")

    with patch.object(smod.os, "replace", side_effect=replace_then_fail):
        with pytest.raises(OSError):
            store.put(Session(user_id=2, name="new"))
    # File is valid; it may be old or new, but never corrupt.
    loaded = SessionStore(p, password=PW).load_all()
    assert "user:1" in loaded or "user:2" in loaded


def test_temp_file_cleaned_on_write_failure(tmp_path):
    p = tmp_path / "s.session"
    store = SessionStore(p, password=PW)

    # شکست در حین نوشتن فایل موقت (fsync داخل بلوک نوشتن) باید موقت را پاک
    # کند و فایل اصلی را دستنخورده بگذارد.
    def fail_fsync(fd):
        raise OSError("disk full")

    with patch.object(smod.os, "fsync", side_effect=fail_fsync):
        with pytest.raises(OSError):
            store.put(Session(user_id=1))
    temps = [f for f in tmp_path.iterdir() if ".tmp" in f.name]
    assert temps == []


def test_corrupt_temp_does_not_affect_live(tmp_path):
    p = tmp_path / "s.session"
    store = SessionStore(p, password=PW)
    store.put(Session(user_id=1, name="original"))
    original = p.read_bytes()
    (tmp_path / "s.session.fake.tmp").write_bytes(b"garbage")
    assert p.read_bytes() == original
    assert store.load_all()["user:1"].name == "original"


def test_permission_error_keeps_original(tmp_path):
    p = tmp_path / "s.session"
    store = SessionStore(p, password=PW)
    store.put(Session(user_id=1, name="original"))
    original = p.read_bytes()
    with patch.object(smod.os, "replace", side_effect=PermissionError("denied")):
        with pytest.raises(PermissionError):
            store.put(Session(user_id=2))
    assert p.read_bytes() == original


def test_incomplete_session_file_rejected(tmp_path):
    p = tmp_path / "s.session"
    p.write_bytes(MAGIC_V2 + MODE_AESGCM_V3 + b"\x00" * 5)
    with pytest.raises(SessionError):
        SessionStore(p, password=PW).load_all()


# --- concurrency (threads share the per-path RLock) ---

def test_concurrent_save_threads(tmp_path):
    p = tmp_path / "s.session"
    store = SessionStore(p, password=PW)
    errors = []

    def writer(i):
        try:
            store.put(Session(user_id=i, name=f"u{i}"))
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    loaded = SessionStore(p, password=PW).load_all()
    assert len(loaded) == 20  # no lost update thanks to the lock


def test_concurrent_migration_threads(tmp_path):
    p = tmp_path / "s.session"
    make_legacy(p)
    store = SessionStore(p, password=PW)
    results = []

    def migrate():
        try:
            results.append(SessionStore(p, password=PW).migrate_to_v2())
        except Exception as e:  # pragma: no cover
            results.append(e)

    threads = [threading.Thread(target=migrate) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(r is True or r is False for r in results)
    assert store.format_version(p.read_bytes()) == "BKS3"
    assert store.get("user:1").access_token == "legacy"


def test_concurrent_rollback_threads(tmp_path):
    p = tmp_path / "s.session"
    make_legacy(p)
    original = p.read_bytes()
    store = SessionStore(p, password=PW)
    store.migrate_to_v2()

    def rollback():
        try:
            SessionStore(p, password=PW).rollback_migration()
        except Exception:  # pragma: no cover
            pass

    threads = [threading.Thread(target=rollback) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert p.read_bytes() == original
    assert SessionStore(p, password=PW).get("user:1").access_token == "legacy"


def test_lock_is_reentrant_no_deadlock(tmp_path):
    """A Store operation nested inside another must not deadlock."""
    p = tmp_path / "s.session"
    store = SessionStore(p, password=PW)
    with smod._lock_for(p):
        with smod._lock_for(p):
            store.put(Session(user_id=1))
    assert store.get("user:1") is not None
