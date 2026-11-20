"""Regression tests for the independent adversarial audit findings.

Every test here reproduces a CONFIRMED defect found by reading source and
running a throwaway reproduction script on 2026-11-20.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path

import pytest

from badking.hybrid.session import (
    MAGIC_V1,
    MODE_XOR_HMAC,
    Session,
    SessionError,
    SessionStore,
    _derive_key,
    _xor_stream,
)
from badking.hybrid.transport import Transport

PW = "pw-strong-1234"


def make_legacy(path, password=PW, uid=7):
    payload = json.dumps(
        {"version": 1, "sessions": {f"user:{uid}": {"access_token": "legacy", "user_id": uid}}}
    ).encode()
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    body = _xor_stream(payload, key)
    mac = hmac.new(key, body, hashlib.sha256).digest()
    path.write_bytes(MAGIC_V1 + MODE_XOR_HMAC + salt + mac + body)


# --- F1: rollback with corrupt-but-valid-header backup ---

def test_rollback_rejects_corrupt_backup(tmp_path):
    p = tmp_path / "s.session"
    make_legacy(p)
    s = SessionStore(p, password=PW)
    s.migrate_to_v2()
    good = p.read_bytes()
    bak = Path(str(p) + ".bak")
    b = bytearray(bak.read_bytes())
    b[60] ^= 0xFF  # corrupt body, keep 6-byte magic intact
    bak.write_bytes(bytes(b))

    with pytest.raises(SessionError):
        s.rollback_migration()
    # Live file must remain the good BKS2 session.
    assert p.read_bytes() == good
    assert s.load_all()


# --- F2: raw exception from malformed session value ---

def test_malformed_session_value_raises_session_error(tmp_path):
    p = tmp_path / "s.session"
    p.write_bytes(b"BKS1\x00" + b'{"version":2,"sessions":{"x":123}}')
    with pytest.raises(SessionError):
        SessionStore(p).load_all()


def test_unreadable_path_raises_session_error(tmp_path):
    d = tmp_path / "adir"
    d.mkdir()
    with pytest.raises(SessionError):
        SessionStore(d).load_all()


# --- F3: token repr leak ---

def test_session_repr_does_not_leak_secrets():
    s = Session(access_token="SUPER_SECRET_TOKEN", refresh_token="REFRESH_SECRET", phone="09123456789")
    r = repr(s)
    assert "SUPER_SECRET_TOKEN" not in r
    assert "REFRESH_SECRET" not in r
    assert "09123456789" not in r


# --- F4: plaintext injection when password is set ---

def test_plain_file_rejected_when_password_set(tmp_path):
    p = tmp_path / "s.session"
    p.write_bytes(
        b"BKS1\x00"
        + b'{"version":2,"sessions":{"user:1":{"access_token":"ATTACKER","user_id":1}}}'
    )
    with pytest.raises(SessionError):
        SessionStore(p, password="anything").get("user:1")


def test_plain_migration_still_works(tmp_path):
    """Legacy plain file must remain migratable with explicit allow_plain."""
    p = tmp_path / "s.session"
    p.write_bytes(
        b"BKS1\x00"
        + b'{"version":2,"sessions":{"user:1":{"access_token":"OLD","user_id":1}}}'
    )
    s = SessionStore(p, password=PW)
    assert s.migrate_to_v2() is True
    assert s.format_version(p.read_bytes()) == "BKS2"
    assert s.get("user:1").access_token == "OLD"


# --- F5/F6: FIFO unsafe by default ---

@pytest.mark.asyncio
async def test_strict_correlation_does_not_misattribute_late_response():
    t = Transport("ws://x", stamp_req_id=False)
    loop = asyncio.get_event_loop()
    fb = loop.create_future()
    t._pending = {"b": fb}
    t._fifo = []  # strict: nothing queued
    await t._dispatch(b"late-response-for-a")
    assert not fb.done()  # must NOT be attributed to b


@pytest.mark.asyncio
async def test_strict_correlation_routes_unsolicited_to_update():
    t = Transport("ws://x", stamp_req_id=False)
    loop = asyncio.get_event_loop()
    fa = loop.create_future()
    t._pending = {"a": fa}
    t._fifo = []
    updates = []

    async def on_update(frame):
        updates.append(frame)

    t.on_update = on_update
    await t._dispatch(b"unsolicited-update")
    assert not fa.done()
    assert updates == [b"unsolicited-update"]


# --- F7: session file permissions (0600 on POSIX) ---

def test_session_file_created_with_restricted_permissions(tmp_path):
    import sys
    if sys.platform.startswith("win"):
        pytest.skip("POSIX permission semantics not applicable on Windows")
    p = tmp_path / "s.session"
    SessionStore(p, password=PW).put(Session(user_id=1))
    mode = p.stat().st_mode & 0o777
    assert mode == 0o600
