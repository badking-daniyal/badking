"""تستهای امنیتی Session: AEAD، Migration، Isolation، Concurrent."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time

import pytest

from badking.hybrid.session import (
    MAGIC_V1,
    MAGIC_V2,
    MODE_AESGCM,
    MODE_PLAIN,
    MODE_XOR_HMAC,
    PBKDF2_ROUNDS,
    Session,
    SessionError,
    SessionStore,
    _derive_key,
    _xor_stream,
)

PASSWORD = "a-strong-session-password-1234"


def _make_legacy_v1(path, *, password=PASSWORD, user_id=7):
    """ساخت session با فرمت قدیمی XOR+HMAC (شبیهسازی واقعی)."""
    payload = json.dumps(
        {
            "version": 1,
            "sessions": {
                f"user:{user_id}": {
                    "access_token": "legacy.token.value",
                    "user_id": user_id,
                    "phone": "09123456789",
                    "name": "Legacy",
                }
            },
        }
    ).encode("utf-8")
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    body = _xor_stream(payload, key)
    mac = hmac.new(key, body, hashlib.sha256).digest()
    path.write_bytes(MAGIC_V1 + MODE_XOR_HMAC + salt + mac + body)
    return path


def _make_legacy_plain(path, user_id=3):
    payload = json.dumps(
        {
            "version": 1,
            "sessions": {
                f"user:{user_id}": {
                    "access_token": "plain.token",
                    "user_id": user_id,
                }
            },
        }
    ).encode("utf-8")
    path.write_bytes(MAGIC_V1 + MODE_PLAIN + payload)
    return path


# ---------- 1. Valid Session ----------

def test_valid_session_roundtrip(tmp_path):
    path = tmp_path / "v2.session"
    store = SessionStore(path, password=PASSWORD)
    store.put(Session(access_token="a.b.c", user_id=1, name="Test"))
    assert store.format_version(path.read_bytes()) == "BKS2"
    loaded = SessionStore(path, password=PASSWORD).get("user:1")
    assert loaded is not None
    assert loaded.name == "Test"
    assert loaded.access_token == "a.b.c"


# ---------- 2. Invalid Key ----------

def test_invalid_key_rejected(tmp_path):
    path = tmp_path / "v2.session"
    SessionStore(path, password=PASSWORD).put(Session(user_id=1))
    with pytest.raises(SessionError):
        SessionStore(path, password="wrong-password").load_all()


# ---------- 3. Modified Ciphertext ----------

def test_modified_ciphertext_rejected(tmp_path):
    path = tmp_path / "v2.session"
    SessionStore(path, password=PASSWORD).put(Session(user_id=1))
    blob = bytearray(path.read_bytes())
    # آخرین بایت ciphertext/tag را عوض میکنیم
    blob[-1] ^= 0xFF
    path.write_bytes(bytes(blob))
    with pytest.raises(SessionError, match="دستکاری|رمز"):
        SessionStore(path, password=PASSWORD).load_all()


# ---------- 4. Invalid Authentication Tag ----------

def test_invalid_auth_tag_rejected(tmp_path):
    path = tmp_path / "v2.session"
    SessionStore(path, password=PASSWORD).put(Session(user_id=1))
    blob = bytearray(path.read_bytes())
    # بایت tag (آخرین ۱۶ بایت) را دستکاری میکنیم
    blob[-16] ^= 0x01
    path.write_bytes(bytes(blob))
    with pytest.raises(SessionError):
        SessionStore(path, password=PASSWORD).load_all()


# ---------- 5. Invalid Nonce ----------

def test_invalid_nonce_length_rejected(tmp_path):
    path = tmp_path / "v2.session"
    SessionStore(path, password=PASSWORD).put(Session(user_id=1))
    blob = bytearray(path.read_bytes())
    # nonce را کوتاه میکنیم: header 5+16+12=33 بایت است
    path.write_bytes(bytes(blob[:32]) + bytes(blob[33:]))
    with pytest.raises(SessionError):
        SessionStore(path, password=PASSWORD).load_all()


def test_nonce_is_random_and_unique(tmp_path):
    path1 = tmp_path / "a.session"
    path2 = tmp_path / "b.session"
    SessionStore(path1, password=PASSWORD).put(Session(user_id=1))
    SessionStore(path2, password=PASSWORD).put(Session(user_id=1))
    n1 = path1.read_bytes()[21:33]
    n2 = path2.read_bytes()[21:33]
    assert len(n1) == 12
    assert n1 != n2  # nonce تکراری نیست


# ---------- 6. Corrupted Session ----------

@pytest.mark.parametrize("bad", [b"", b"garbage", MAGIC_V1 + MODE_PLAIN + b"{bad json"])
def test_corrupted_session_rejected(tmp_path, bad):
    path = tmp_path / "bad.session"
    path.write_bytes(bad)
    with pytest.raises(SessionError):
        SessionStore(path, password=PASSWORD).load_all()


def test_header_is_aad_protected(tmp_path):
    """دستکاری salt/nonce (header) باعث شکست auth میشود."""
    path = tmp_path / "v2.session"
    SessionStore(path, password=PASSWORD).put(Session(user_id=1))
    blob = bytearray(path.read_bytes())
    blob[5] ^= 0xFF  # salt دستکاری شد
    path.write_bytes(bytes(blob))
    with pytest.raises(SessionError):
        SessionStore(path, password=PASSWORD).load_all()


# ---------- 7. Legacy Session Migration ----------

def test_legacy_v1_migration(tmp_path):
    path = _make_legacy_v1(tmp_path / "old.session")
    store = SessionStore(path, password=PASSWORD)
    assert store.format_version(path.read_bytes()) == "BKS1-encrypted"
    assert store.needs_migration() is True
    assert store.migrate_to_v2() is True
    assert store.format_version(path.read_bytes()) == "BKS2"
    loaded = SessionStore(path, password=PASSWORD).get("user:7")
    assert loaded.name == "Legacy"
    assert loaded.access_token == "legacy.token.value"
    assert (tmp_path / "old.session.bak").exists()  # بکاپ امن ساخته شد


def test_migration_is_idempotent(tmp_path):
    path = _make_legacy_v1(tmp_path / "old.session")
    store = SessionStore(path, password=PASSWORD)
    assert store.migrate_to_v2() is True
    assert store.migrate_to_v2() is False  # دومین بار کاری نمیکند


def test_legacy_plain_migration_requires_password(tmp_path):
    path = _make_legacy_plain(tmp_path / "plain.session")
    store = SessionStore(path, password=None)
    with pytest.raises(SessionError, match="رمز"):
        store.migrate_to_v2()


# ---------- 8. Migration Failure ----------

def test_migration_failure_keeps_original(tmp_path):
    """رمز اشتباه → migration شکست میخورد ولی فایل اصلی سالم میماند."""
    path = _make_legacy_v1(tmp_path / "old.session", password=PASSWORD)
    original = path.read_bytes()
    store = SessionStore(path, password="wrong-password")
    with pytest.raises(SessionError):
        store.migrate_to_v2()
    assert path.read_bytes() == original  # دست نخورده


def test_rollback_migration(tmp_path):
    path = _make_legacy_v1(tmp_path / "old.session")
    original = path.read_bytes()
    store = SessionStore(path, password=PASSWORD)
    store.migrate_to_v2()
    assert store.format_version(path.read_bytes()) == "BKS2"
    assert store.rollback_migration() is True
    assert path.read_bytes() == original  # بازگشت دقیق بایت به بایت


def test_rollback_without_backup_returns_false(tmp_path):
    path = tmp_path / "v2.session"
    SessionStore(path, password=PASSWORD).put(Session(user_id=1))
    assert SessionStore(path, password=PASSWORD).rollback_migration() is False


# ---------- 9. Key Rotation ----------

def test_key_rotation(tmp_path):
    """تغییر رمز: با رمز قدیمی نمیشود خواند، با رمز جدید ذخیره میشود."""
    path = tmp_path / "rotate.session"
    SessionStore(path, password="old-password").put(Session(user_id=1))
    data = SessionStore(path, password="old-password").load_all()
    SessionStore(path, password="new-password").save_all(data)
    with pytest.raises(SessionError):
        SessionStore(path, password="old-password").load_all()
    assert SessionStore(path, password="new-password").get("user:1") is not None


def test_pbkdf2_parameters():
    assert PBKDF2_ROUNDS >= 100_000
    k1 = _derive_key("pass", b"salt")
    k2 = _derive_key("pass", b"salt")
    k3 = _derive_key("pass", b"other")
    assert k1 == k2 and len(k1) == 32
    assert k1 != k3


# ---------- 10. Multi-account Isolation ----------

def test_multi_account_isolation(tmp_path):
    path = tmp_path / "multi.session"
    store = SessionStore(path, password=PASSWORD)
    store.put(Session(access_token="a", user_id=1, phone="09111111111"))
    store.put(Session(access_token="b", user_id=2, phone="09222222222"))
    assert store.get("user:1").access_token == "a"
    assert store.get("user:2").access_token == "b"
    assert store.get("user:1") is not store.get("user:2")
    assert len(store.list_accounts()) == 2


def test_unauthorized_session_access(tmp_path):
    """دسترسی به کلید اکانت دیگر وجود ندارد."""
    path = tmp_path / "multi.session"
    store = SessionStore(path, password=PASSWORD)
    store.put(Session(user_id=1))
    assert store.get("user:999") is None


# ---------- 11. Concurrent Access ----------

@pytest.mark.asyncio
async def test_concurrent_access(tmp_path):
    """چند نویسنده همزمان — آخرین نوشته سالم و قابل خواندن است."""
    path = tmp_path / "concurrent.session"
    store = SessionStore(path, password=PASSWORD)

    async def write(uid):
        await asyncio.sleep(0)
        store.put(Session(user_id=uid, name=f"user{uid}"))

    await asyncio.gather(*(write(i) for i in range(10)))
    loaded = SessionStore(path, password=PASSWORD).load_all()
    assert len(loaded) >= 1
    # فایل نهایی معتبر است (دستکاری نشده)
    assert store.format_version(path.read_bytes()) == "BKS2"


# ---------- 12. Regression: plain mode still works ----------

def test_plain_mode_regression(tmp_path):
    """حالت بدون رمز (رفتار قدیمی) تغییر نکرده است."""
    path = tmp_path / "plain.session"
    store = SessionStore(path)
    store.put(Session(user_id=42, name="Danial"))
    assert store.format_version(path.read_bytes()) == "BKS1-plain"
    assert SessionStore(path).get("user:42").name == "Danial"
