"""مدیریت session و اکانت‌های self-bot.

هر session یک اکانت شخصی بله است: access_token (JWT)، اطلاعات کاربر، و
دستگاه. فایل session رمزنگاریشده روی دیسک ذخیره میشود تا ری‌استارت بدون
کد SMS کار کند.

فرمت فایل (نسخهبندی شده):
    ``BKS1\\x00<payload>``   → قدیمی، رمزنگاری نشده ( Plain ) — فقط برای سازگاری
    ``BKS1\\x01<salt><mac><body>`` → قدیمی، XOR+HMAC دستساز — فقط خواندن
    ``BKS2\\x02<salt><nonce><ciphertext+tag>`` → جدید، AES-256-GCM (AEAD)

چرا AEAD؟
    فرمت قدیمی دو مشکل واقعی داشت: (۱) استریم XOR دستساز بود، (۲) HMAC فقط
    بدنه را میپوشاند و header (salt/mode) محافظتنشده بود. AES-GCM هم
    محرمانگی و هم یکپارچگی را با Authentication Tag تأمین میکند و header
    را بهعنوان AAD احراز میکند.

هشدار: self-bot غیررسمی است؛ استفاده یعنی پذیرش ریسک مسدود شدن اکانت.
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


# ---------- ثوابت فرمت ----------

MAGIC_V1 = b"BKS1"          # فرمت قدیمی (plain و XOR+HMAC)
MAGIC_V2 = b"BKS2"          # فرمت جدید (AES-GCM)
MODE_PLAIN = b"\x00"
MODE_XOR_HMAC = b"\x01"     # قدیمی، فقط خواندن
MODE_AESGCM = b"\x02"       # جدید

SALT_LEN = 16
NONCE_LEN = 12              # nonce استاندارد GCM (96 بیت)
TAG_LEN = 16                # Authentication Tag استاندارد GCM
PBKDF2_ROUNDS = 200_000


def _derive_key(password: str, salt: bytes) -> bytes:
    """کلید ۲۵۶ بیتی مشتقشده با PBKDF2-HMAC-SHA256 (استاندارد)."""
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS, dklen=32
    )


def _xor_stream(data: bytes, key: bytes) -> bytes:
    """استریم XOR قدیمی — فقط برای خواندن sessionهای BKS1."""
    out = bytearray(len(data))
    block = b""
    counter = 0
    for i, byte in enumerate(data):
        if i % 32 == 0:
            block = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha256).digest()
            counter += 1
        out[i] = byte ^ block[i % 32]
    return bytes(out)


def _load_aesgcm():
    """بارگذاری AESGCM با خطای امن (بدون افشای جزئیات)."""
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover - وابستگی اختیاری hybrid
        raise SessionError(
            "برای session رمزنگاریشده بسته cryptography لازم است"
        ) from exc
    return AESGCM, InvalidTag


@dataclass
class Session:
    """یک اکانت self-bot.

    فیلدهای حساس (access_token / refresh_token / phone) با ``repr=False``
    تعریف شدهاند تا در لاگها، tracebackها و خروجی debugger نشت نکنند.
    """

    access_token: str = field(default="", repr=False)
    refresh_token: str = field(default="", repr=False)
    user_id: int | None = None
    phone: str = field(default="", repr=False)
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
        """زمان انقضای JWT از payload، بدون verify امضا.

        نکته امنیتی: این تابع فقط برای نمایش/تصمیمگیری محلی است و امضا را
        تأیید نمیکند. جهت تأیید واقعی از ``JWTVerifier`` استفاده کن.
        """
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
        if not isinstance(data, dict):
            raise SessionError("ورودی session نامعتبر است")
        known = {f for f in cls.__dataclass_fields__}
        try:
            return cls(**{k: v for k, v in data.items() if k in known})
        except (TypeError, ValueError) as exc:
            # بدون افشای محتوا — فقط نوع خطا مشخص میشود.
            raise SessionError("ساختار session نامعتبر است") from None


class SessionStore:
    """ذخیره و بازیابی session ها روی دیسک، با پشتیبانی چند اکانت.

    نوشتن همیشه با ``BKS2`` (AES-GCM) انجام میشود وقتی رمز داده شده باشد.
    خواندن از هر سه فرمت قدیمی و جدید پشتیبانی میکند تا sessionهای موجود
    ناگهان غیرقابلاستفاده نشوند.
    """

    MAGIC = MAGIC_V1  # سازگاری با کدی که به SessionStore.MAGIC referencه میدهد

    def __init__(self, path: str | Path = "badking.session", password: str | None = None):
        self.path = Path(path)
        self.password = password or os.environ.get("BADKING_SESSION_KEY", "")
        self._cache: dict[str, Session] = {}

    # ---------- تشخیص فرمت ----------

    @staticmethod
    def format_version(blob: bytes) -> str:
        """نسخه فرمت فایل را بدون رمزگشایی تشخیص میدهد."""
        if blob.startswith(MAGIC_V2 + MODE_AESGCM):
            return "BKS2"
        if blob.startswith(MAGIC_V1 + MODE_XOR_HMAC):
            return "BKS1-encrypted"
        if blob.startswith(MAGIC_V1 + MODE_PLAIN):
            return "BKS1-plain"
        raise SessionError("فایل session معتبر نیست (magic/namespace اشتباه)")

    # ---------- رمزنگاری ----------

    def _encrypt(self, plaintext: bytes) -> bytes:
        """رمزنگاری با AES-256-GCM (فرمت BKS2)."""
        if not self.password:
            # حالت بدون رمز: قدیمی و رمزنگارینشده باقی میماند تا تستها و
            # کاربران فعلی نشکنند. صریحاً ناامن است — مستند شده.
            return MAGIC_V1 + MODE_PLAIN + plaintext
        AESGCM, _ = _load_aesgcm()
        salt = os.urandom(SALT_LEN)
        nonce = os.urandom(NONCE_LEN)  # nonce تصادفی و غیرتکراری
        key = _derive_key(self.password, salt)
        header = MAGIC_V2 + MODE_AESGCM + salt + nonce
        # AAD = header → دستکاری salt/nonce/نسخه باعث شکست auth میشود.
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, header)
        return header + ciphertext  # tag توسط AESGCM به انتها اضافه میشود

    def _decrypt(self, blob: bytes, *, allow_plain: bool = False) -> bytes:
        """رمزگشایی امن با پشتیبانی از فرمتهای قدیمی.

        Args:
            allow_plain: خواندن فرمت رمزنگارینشده BKS1-plain. فقط زمانی که
                رمز تنظیم شده، مهاجم با دسترسی نوشتن میتوانست فایل رمزدار
                را با یک فایل plain جعلی جایگزین کند و بدون رمز، توکن دلخواه
                تزریق نماید. به همین دلیل خواندن plain وقتی password وجود
                دارد، تنها با اجازه صریح (مثلاً در migration) مجاز است.
        """
        version = self.format_version(blob)

        if version == "BKS1-plain":
            if self.password and not allow_plain:
                raise SessionError(
                    "فایل session رمزنگاری نشده است در حالی که رمز تنظیم شده؛ "
                    "برای تبدیل آن migrate_to_v2() را صدا بزن"
                )
            return blob[5:]

        if version == "BKS1-encrypted":
            # فرمت قدیمی XOR+HMAC — فقط برای خواندن، جهت migration.
            if not self.password:
                raise SessionError(
                    "این session رمز دارد؛ BADKING_SESSION_KEY را تنظیم کن"
                )
            salt = blob[5:21]
            mac = blob[21:53]
            body = blob[53:]
            key = _derive_key(self.password, salt)
            expected = hmac.new(key, body, hashlib.sha256).digest()
            if not hmac.compare_digest(mac, expected):
                raise SessionError("رمز session اشتباه است یا فایل دستکاری شده")
            return _xor_stream(body, key)

        # BKS2 — AES-GCM
        if not self.password:
            raise SessionError(
                "این session رمز دارد؛ BADKING_SESSION_KEY را تنظیم کن"
            )
        AESGCM, InvalidTag = _load_aesgcm()
        salt = blob[5:21]
        nonce = blob[21:33]
        ciphertext = blob[33:]
        header = blob[:33]
        if len(nonce) != NONCE_LEN or len(ciphertext) < TAG_LEN:
            raise SessionError("فایل session ناقص است")
        key = _derive_key(self.password, salt)
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, header)
        except InvalidTag:
            # پیام عمومی — جزئیات امضا/کلید افشا نمیشود.
            raise SessionError("فایل session دستکاری شده یا رمز اشتباه است") from None
        except Exception:
            raise SessionError("فایل session قابل رمزگشایی نیست") from None

    # ---------- I/O ----------

    def load_all(self, *, allow_plain: bool = False) -> dict[str, Session]:
        if not self.path.exists():
            return {}
        try:
            blob = self.path.read_bytes()
        except OSError:
            raise SessionError("فایل session قابل خواندن نیست") from None
        try:
            data = json.loads(self._decrypt(blob, allow_plain=allow_plain).decode("utf-8"))
        except SessionError:
            raise
        except Exception:
            # JSON خراب / utf-8 نامعتبر — پیام امن، بدون افشای محتوا.
            raise SessionError("فایل session خراب است") from None
        if not isinstance(data, dict) or not isinstance(data.get("sessions"), dict):
            raise SessionError("ساختار فایل session نامعتبر است")
        out: dict[str, Session] = {}
        for key, raw in data.get("sessions", {}).items():
            out[key] = Session.from_dict(raw)
        self._cache = out
        return out

    def save_all(self, sessions: dict[str, Session]) -> None:
        payload = json.dumps(
            {"version": 2, "sessions": {k: v.to_dict() for k, v in sessions.items()}},
            ensure_ascii=False,
        ).encode("utf-8")
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        data = self._encrypt(payload)
        # مجوز محدود از همان لحظه ایجاد فایل موقت (0600 روی یونیکس).
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        os.replace(tmp, self.path)  # اتمیک
        try:
            os.chmod(self.path, 0o600)
        except OSError:  # Windows — مجوز یونیکس قابل اعمال نیست
            pass
        self._cache = dict(sessions)

    # ---------- Migration ----------

    def needs_migration(self) -> bool:
        """آیا فایل فعلی فرمت قدیمی رمزنگاریشده است؟"""
        if not self.path.exists():
            return False
        return self.format_version(self.path.read_bytes()) == "BKS1-encrypted"

    def backup(self, suffix: str = ".bak") -> Path:
        """بکاپ امن قبل از migration.

        فایل بکاپ با مجوز 0600 (روی سیستمهای یونیکس) نوشته میشود تا فقط
        مالک قابل خواندن باشد. فایل اصلی حذف یا تغییر نمیشود.
        """
        if not self.path.exists():
            raise SessionError("فایلی برای بکاپ وجود ندارد")
        backup_path = self.path.with_suffix(self.path.suffix + suffix)
        data = self.path.read_bytes()
        # نوشتن اتمیک + محدود کردن مجوز
        tmp = backup_path.with_suffix(backup_path.suffix + ".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        os.replace(tmp, backup_path)
        try:
            os.chmod(backup_path, 0o600)
        except OSError:  # Windows — مجوز یونیکس قابل اعمال نیست
            pass
        return backup_path

    def migrate_to_v2(self, *, backup: bool = True) -> bool:
        """تبدیل ``BKS1-encrypted`` به ``BKS2`` (AES-GCM).

        ایمنی:
            - قبل از تبدیل بکاپ گرفته میشود (پیشفرض).
            - ابتدا فایل قدیمی رمزگشایی میشود؛ اگر ناموفق بود، فایل اصلی
              دست نخورده باقی میماند.
            - نوشتن فایل جدید اتمیک است (os.replace).
            - قابلتکرار است: اگر از قبل BKS2 باشد، ``False`` برمیگرداند.
            - Rollback: بکاپ ``<path>.bak`` است؛ ``rollback_migration()``
              آنرا برمیگرداند.

        Returns:
            ``True`` اگر تبدیل انجام شد، ``False`` اگر نیازی نبود.
        """
        if not self.path.exists():
            return False
        version = self.format_version(self.path.read_bytes())
        if version == "BKS2":
            return False
        if version == "BKS1-plain":
            # فایل plain را به AES-GCM تبدیل میکنیم اگر رمز داریم.
            if not self.password:
                raise SessionError(
                    "برای migration فایل plain باید رمز (password) تنظیم شود"
                )
        if backup:
            self.backup()

        # ۱) رمزگشایی فایل قدیمی (در صورت شکست، اصلی دست نخورده میماند).
        #    اجازه صریح plain فقط در مسیر migration داده میشود تا فایل
        #    قدیمی قابل تبدیل بماند، بدون اینکه خواندن عادی فایل plain جعلی
        #    را ممکن کند.
        sessions = self.load_all(allow_plain=True)
        # ۲) نوشتن اتمیک با فرمت جدید
        self.save_all(sessions)
        self._cache = dict(sessions)
        return True

    def rollback_migration(self, backup_path: str | Path | None = None) -> bool:
        """بازگردانی بکاپ قبل از migration.

        Returns:
            ``True`` اگر بکاپ پیدا و بازگردانده شد، ``False`` در غیر اینصورت.
        """
        backup_path = Path(backup_path) if backup_path else self.path.with_suffix(
            self.path.suffix + ".bak"
        )
        if not backup_path.exists():
            return False
        data = backup_path.read_bytes()

        # تأیید کامل بکاپ قبل از جایگزینی. چک کردن تنها ۶ بایت magic کافی
        # نیست: یک بکاپ با header سالم و بدنه خراب، فایل زنده سالم را با
        # داده غیرقابلخواندن جایگزین میکرد. اینجا بکاپ واقعاً رمزگشایی
        # میشود تا HMAC / GCM tag / JSON هم تأیید شوند.
        probe = SessionStore(backup_path, password=self.password)
        probe.load_all(allow_plain=True)  # در صورت خرابی SessionError — فایل زنده دست نخورده میماند

        tmp = self.path.with_suffix(self.path.suffix + ".rollback")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, self.path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        self._cache = {}
        return True

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
