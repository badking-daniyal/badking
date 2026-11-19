"""مدیریت session و اکانت‌های self-bot.

هر session یک اکانت شخصی بله است: access_token (JWT)، اطلاعات کاربر، و
دستگاه. فایل session رمزنگاری‌شده روی دیسک ذخیره می‌شود تا ری‌استارت بدون
کد SMS کار کند.

هشدار: این لایه با API داخلی بله کار می‌کند که غیررسمی است. استفاده یعنی
پذیرش ریسک مسدود شدن اکانت.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


class SessionError(Exception):
    """خطای session: فایل خراب، رمز اشتباه، یا توکن منقضی."""


def _derive_key(password: str, salt: bytes) -> bytes:
    """کلید مشتق‌شده با PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000, dklen=32)


def _xor_stream(data: bytes, key: bytes) -> bytes:
    """استریم XOR با کلید مشتق‌شده (برای مخفی‌سازی at-rest، نه رمزنگاری قوی)."""
    out = bytearray(len(data))
    block = b""
    counter = 0
    for i, byte in enumerate(data):
        if i % 32 == 0:
            block = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha256).digest()
            counter += 1
        out[i] = byte ^ block[i % 32]
    return bytes(out)


@dataclass
class Session:
    """یک اکانت self-bot."""

    access_token: str = ""
    refresh_token: str = ""
    user_id: int | None = None
    phone: str = ""
    name: str = ""
    username: str = ""
    device_model: str = "BADKING"
    app_version: str = "1.0.0"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """آیا توکن داریم و منقضی نشده؟"""
        if not self.access_token:
            return False
        exp = self.token_expiry()
        if exp is None:
            return True
        return exp > time.time() + 30

    def token_expiry(self) -> float | None:
        """زمان انقضای JWT از payload، بدون verify امضا."""
        parts = self.access_token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        try:
            raw = base64.urlsafe_b64decode(payload)
            data = json.loads(raw)
        except Exception:
            return None
        exp = data.get("exp")
        return float(exp) if exp else None

    def touch(self) -> None:
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


class SessionStore:
    """ذخیره و بازیابی session ها روی دیسک، با پشتیبانی چند اکانت."""

    MAGIC = b"BKS1"

    def __init__(self, path: str | Path = "badking.session", password: str | None = None):
        self.path = Path(path)
        self.password = password or os.environ.get("BADKING_SESSION_KEY", "")
        self._cache: dict[str, Session] = {}

    # ---------- رمزنگاری ----------
    def _encrypt(self, plaintext: bytes) -> bytes:
        if not self.password:
            return self.MAGIC + b"\x00" + plaintext
        salt = os.urandom(16)
        key = _derive_key(self.password, salt)
        body = _xor_stream(plaintext, key)
        mac = hmac.new(key, body, hashlib.sha256).digest()
        return self.MAGIC + b"\x01" + salt + mac + body

    def _decrypt(self, blob: bytes) -> bytes:
        if not blob.startswith(self.MAGIC):
            raise SessionError("فایل session معتبر نیست (magic اشتباه)")
        mode = blob[4:5]
        if mode == b"\x00":
            return blob[5:]
        if mode != b"\x01":
            raise SessionError("نسخه فایل session پشتیبانی نمی‌شود")
        if not self.password:
            raise SessionError("این session رمز دارد؛ BADKING_SESSION_KEY را تنظیم کن")
        salt = blob[5:21]
        mac = blob[21:53]
        body = blob[53:]
        key = _derive_key(self.password, salt)
        expected = hmac.new(key, body, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected):
            raise SessionError("رمز session اشتباه است یا فایل دستکاری شده")
        return _xor_stream(body, key)

    # ---------- I/O ----------
    def load_all(self) -> dict[str, Session]:
        if not self.path.exists():
            return {}
        blob = self.path.read_bytes()
        data = json.loads(self._decrypt(blob).decode("utf-8"))
        out: dict[str, Session] = {}
        for key, raw in data.get("sessions", {}).items():
            out[key] = Session.from_dict(raw)
        self._cache = out
        return out

    def save_all(self, sessions: dict[str, Session]) -> None:
        payload = json.dumps(
            {"version": 1, "sessions": {k: v.to_dict() for k, v in sessions.items()}},
            ensure_ascii=False,
        ).encode("utf-8")
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_bytes(self._encrypt(payload))
        os.replace(tmp, self.path)  # اتمیک
        self._cache = dict(sessions)

    # ---------- API ----------
    @staticmethod
    def key_for(session: Session) -> str:
        if session.user_id:
            return f"user:{session.user_id}"
        if session.phone:
            return f"phone:{session.phone}"
        return "default"

    def get(self, key: str = "default") -> Session | None:
        if not self._cache:
            self.load_all()
        return self._cache.get(key)

    def put(self, session: Session) -> str:
        sessions = self._cache or self.load_all()
        key = self.key_for(session)
        session.touch()
        sessions[key] = session
        self.save_all(sessions)
        return key

    def delete(self, key: str) -> bool:
        sessions = self._cache or self.load_all()
        if key not in sessions:
            return False
        del sessions[key]
        self.save_all(sessions)
        return True

    def list_accounts(self) -> list[dict[str, Any]]:
        sessions = self._cache or self.load_all()
        return [
            {
                "key": k,
                "user_id": s.user_id,
                "phone": s.phone,
                "name": s.name,
                "username": s.username,
                "valid": s.is_valid(),
            }
            for k, s in sessions.items()
        ]
