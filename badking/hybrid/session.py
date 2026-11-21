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
import contextlib
import hashlib
import hmac
import json
import os
import threading
import time
import weakref
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterator


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
PBKDF2_ROUNDS = 200_000     # پیشفرض قدیمی — فقط برای خواندن فایلهای BKS2 قدیمی
PBKDF2_ROUNDS_V3 = 600_000  # پیشفرض جدید (متناسب با توصیه OWASP 2023)
MIN_PBKDF2_ROUNDS = 100_000  # کف امن برای هدرهای versioned
MAX_PBKDF2_ROUNDS = 5_000_000  # سقف جلوگیری از DoS توسط هدر دستکاریشده

# BKS2 قدیمی: ``BKS2\x02<salt16><nonce12><ciphertext+tag>`` — هدر ۳۳ بایتی.
# BKS3 جدید: ``BKS2\x03<rounds:4 big-endian><salt16><nonce12><ct+tag>`` — هدر ۳۷ بایتی.
# تعداد iteration داخل هدر (و AAD) ذخیره میشود تا فایلهای قدیمی با 200k
# قابل خواندن بمانند و فایلهای جدید با 600k ساخته شوند — مهاجرت تدریجی.
MODE_AESGCM_V3 = b"\x03"
LEGACY_HEADER_LEN = 5 + SALT_LEN + NONCE_LEN   # 33
V3_HEADER_LEN = LEGACY_HEADER_LEN + 4          # 37
ROUNDS_OFFSET = 5                              # بعد از magic(4)+mode(1)


# کش کلید مشتقشده بهازای (password, salt, rounds). PBKDF2 با 600k دور حدود
# 0.6 ثانیه طول میکشد؛ در RMW مکرر همان فایل، salt decryption ثابت است و
# مشتقکردن مجدد کلید بیهوده است. کش فقط در حافظه process است و هرگز روی
# دیسک نوشته نمیشود. محدود به 32 ورودی برای جلوگیری از رشد حافظه.
_KEY_CACHE: dict[tuple[bytes, bytes, int], bytes] = {}
_KEY_CACHE_GUARD = threading.Lock()
_KEY_CACHE_MAX = 32

# شناسهی cache بهجای password خام: HMAC-SHA256 با کلید تصادفی سطح-ماژول.
# هدف: password بهصورت خام و طولانیمدت در حافظه (کلید dict) نماند. این
# شناسه یکطرفه است و کلید مشتقشده را تغییر نمیدهد؛ فقط کلید dict را
# غیرقابل بازگشت میکند. salt تصادفی هر process جداگانه است.
_CACHE_ID_KEY = os.urandom(32)


def _password_cache_id(password: str) -> bytes:
    """شناسه یکطرفه password برای کلید cache (بدون نگهداشتن متن خام)."""
    return hmac.new(_CACHE_ID_KEY, password.encode("utf-8"), hashlib.sha256).digest()


def _derive_key(password: str, salt: bytes, rounds: int = PBKDF2_ROUNDS) -> bytes:
    """کلید ۲۵۶ بیتی مشتقشده با PBKDF2-HMAC-SHA256 (استاندارد).

    ``rounds`` از هدر فایل خوانده میشود؛ پیشفرض همان 200k قدیمی است تا
    فایلهای BKS2 موجود بدون تغییر قابل خواندن بمانند.
    """
    if not MIN_PBKDF2_ROUNDS <= rounds <= MAX_PBKDF2_ROUNDS:
        raise SessionError("تعداد iteration در هدر session نامعتبر است")
    cache_key = (_password_cache_id(password), salt, rounds)
    with _KEY_CACHE_GUARD:
        cached = _KEY_CACHE.get(cache_key)
        if cached is not None:
            return cached
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, rounds, dklen=32
    )
    with _KEY_CACHE_GUARD:
        if len(_KEY_CACHE) >= _KEY_CACHE_MAX:
            _KEY_CACHE.clear()
        _KEY_CACHE[cache_key] = key
    return key


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


# ---------- قفل و نوشتن اتمیک ----------

# دو لایه قفل:
#   ۱) RLock داخل process — هماهنگی threadها و جلوگیری از deadlock ناشی از
#      باز شدن fd جداگانه توسط دو thread (قفل OS مربوط به thread مالک است).
#   ۲) قفل فایل سیستمی (msvcrt/fcntl) روی فایل ``<session>.lock`` — هماهنگی
#      processهای مستقل. فایل قفل هرگز توسط os.replace جایگزین نمیشود.
# ترتیب همیشه RLock سپس قفل فایل است تا deadlock رخ ندهد.
_PATH_LOCKS: weakref.WeakValueDictionary[str, threading.RLock] = (
    weakref.WeakValueDictionary()
)
_PATH_LOCKS_GUARD = threading.Lock()

# حد پیشفرض انتظار برای قفل Between-Process (قابل تنظیم توسط محیط).
# مقدار نامعتبر یا منفی نباید هنگام import کرش کند یا قفل بیانتها صبر کند.
def _read_lock_timeout() -> float:
    raw = os.environ.get("BADKING_SESSION_LOCK_TIMEOUT", "120")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 120.0
    if value < 0 or value != value or value == float("inf"):
        return 120.0
    return value


SESSION_LOCK_TIMEOUT = _read_lock_timeout()


def _lock_for(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[key] = lock
        return lock


@contextlib.contextmanager
def _session_lock(path: Path) -> Iterator[None]:
    """قفل کامل: thread (RLock) + process (فایل قفل پایدار)."""
    from .session_lock import cross_process_lock

    with _lock_for(path):
        with cross_process_lock(path, timeout=SESSION_LOCK_TIMEOUT):
            yield


def _fsync_dir(path: Path) -> None:
    """fsync پوشه بعد از rename (جایی که سیستم پشتیبانی کند).

    روی Windows باز کردن دایرکتوری با os.open معمولاً با خطا مواجه میشود؛
    در آن صورت بیسر و صدن میگذریم — rename خودش اتمیک است.
    """
    try:
        fd = os.open(str(path.parent), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_write(path: Path, data: bytes, *, fsync: bool = True) -> None:
    """نوشتن مقاوم: tmp منحصربهفرد → 0600 → flush → fsync → replace → fsync dir.

    فایل مقصد تا لحظه ``os.replace`` دست نخورده میماند. در صورت هر شکست،
    فایل موقت پاک میشود و استثنا به بالا منتقل میگردد (هیچ ازدستدادن
    بیصدای اطلاعات اصلی).
    """
    tmp = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.{os.urandom(6).hex()}.tmp"
    )
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            if fsync:
                os.fsync(f.fileno())
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    try:
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    if fsync:
        _fsync_dir(path)
    try:
        os.chmod(path, 0o600)
    except OSError:  # Windows — مجوز یونیکس قابل اعمال نیست
        pass


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
        if blob.startswith(MAGIC_V2 + MODE_AESGCM_V3):
            return "BKS3"
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
        rounds = PBKDF2_ROUNDS_V3
        key = _derive_key(self.password, salt, rounds)
        # هدر شامل تعداد iteration هم هست و بهعنوان AAD محافظت میشود.
        header = (
            MAGIC_V2 + MODE_AESGCM_V3 + rounds.to_bytes(4, "big") + salt + nonce
        )
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

        # BKS2 / BKS3 — AES-GCM
        if not self.password:
            raise SessionError(
                "این session رمز دارد؛ BADKING_SESSION_KEY را تنظیم کن"
            )
        AESGCM, InvalidTag = _load_aesgcm()

        if version == "BKS3":
            if len(blob) < V3_HEADER_LEN:
                raise SessionError("فایل session ناقص است")
            rounds = int.from_bytes(blob[ROUNDS_OFFSET:ROUNDS_OFFSET + 4], "big")
            salt = blob[9:25]
            nonce = blob[25:37]
            ciphertext = blob[37:]
            header = blob[:V3_HEADER_LEN]
        else:  # BKS2 قدیمی — هدر ۳۳ بایتی، بدون فیلد rounds
            if len(blob) < LEGACY_HEADER_LEN:
                raise SessionError("فایل session ناقص است")
            rounds = PBKDF2_ROUNDS
            salt = blob[5:21]
            nonce = blob[21:33]
            ciphertext = blob[33:]
            header = blob[:LEGACY_HEADER_LEN]

        if len(nonce) != NONCE_LEN or len(ciphertext) < TAG_LEN:
            raise SessionError("فایل session ناقص است")
        # rounds داخل هدر است و توسط AAD هم محافظت میشود: دستکاری آن یا
        # باعث SessionError (خارج از محدوده) یا شکست GCM tag میشود.
        key = _derive_key(self.password, salt, rounds)
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, header)
        except InvalidTag:
            # پیام عمومی — جزئیات امضا/کلید افشا نمیشود.
            raise SessionError("فایل session دستکاری شده یا رمز اشتباه است") from None
        except Exception:
            raise SessionError("فایل session قابل رمزگشایی نیست") from None

    # ---------- I/O ----------

    def _read_blob_unlocked(self) -> bytes:
        """خواندن خام فایل — فراخواننده باید قفل را نگه دارد."""
        if not self.path.exists():
            self._cache = {}
            return b""
        try:
            return self.path.read_bytes()
        except OSError:
            raise SessionError("فایل session قابل خواندن نیست") from None

    def _decode_blob(self, blob: bytes, *, allow_plain: bool = False) -> dict[str, Session]:
        """رمزگشایی + پارس — کاملاً محلی، نیازی به قفل ندارد.

        PBKDF2 (600k دور) گران است؛ نگه داشتن قفل حین آن باعث starvation
        processهای دیگر میشود. جداسازی آن از قفل، امنیت را کاهش نمیدهد چون
        روی محتوای خواندهشده کار میکند، نه روی فایل زنده.
        """
        if not blob:
            # فقط وقتی فایل اصلاً وجود ندارد مجاز است. فایل موجود و خالی،
            # خراب است و باید SessionError بدهد (رگرسیون امنیتی).
            if self.path.exists():
                raise SessionError("فایل session خالی/خراب است")
            return {}
        try:
            data = json.loads(self._decrypt(blob, allow_plain=allow_plain).decode("utf-8"))
        except SessionError:
            raise
        except Exception:
            raise SessionError("فایل session خراب است") from None
        if not isinstance(data, dict) or not isinstance(data.get("sessions"), dict):
            raise SessionError("ساختار فایل session نامعتبر است")
        return {k: Session.from_dict(v) for k, v in data["sessions"].items()}

    def load_all(self, *, allow_plain: bool = False) -> dict[str, Session]:
        with _session_lock(self.path):
            blob = self._read_blob_unlocked()
            out = self._decode_blob(blob, allow_plain=allow_plain)
            self._cache = out
            return out

    def save_all(self, sessions: dict[str, Session]) -> None:
        # رمزنگاری (PBKDF2) بیرون قفل — فقط نوشتن اتمیک تحت قفل است.
        payload = json.dumps(
            {"version": 2, "sessions": {k: v.to_dict() for k, v in sessions.items()}},
            ensure_ascii=False,
        ).encode("utf-8")
        data = self._encrypt(payload)
        with _session_lock(self.path):
            _atomic_write(self.path, data)
            self._cache = dict(sessions)

    def _rmw_locked(self, mutate) -> Any:
        """Read-Modify-Write کامل تحت قفل thread + process.

        قفل در تمام طول خواندن، رمزگشایی، اعمال تغییر، رمزنگاری و نوشتن
        نگه داشته میشود تا هیچ process دیگری نتواند عملیات را قطع کند.
        """
        with _session_lock(self.path):
            blob = self._read_blob_unlocked()
            sessions = self._decode_blob(blob)
            result = mutate(sessions)
            payload = json.dumps(
                {"version": 2, "sessions": {k: v.to_dict() for k, v in sessions.items()}},
                ensure_ascii=False,
            ).encode("utf-8")
            _atomic_write(self.path, self._encrypt(payload))
            self._cache = dict(sessions)
            return result

    # ---------- Migration ----------

    def needs_migration(self) -> bool:
        """آیا فایل فعلی نیاز به ارتقا دارد (BKS1 یا BKS2 قدیمی)؟"""
        with _session_lock(self.path):
            if not self.path.exists():
                return False
            version = self.format_version(self.path.read_bytes())
            return version in ("BKS1-encrypted", "BKS1-plain", "BKS2")

    def backup(self, suffix: str = ".bak") -> Path:
        """بکاپ امن قبل از migration.

        فایل بکاپ با مجوز 0600 (روی سیستمهای یونیکس) نوشته میشود تا فقط
        مالک قابل خواندن باشد. فایل اصلی حذف یا تغییر نمیشود.
        """
        backup_path = self.path.with_suffix(self.path.suffix + suffix)
        with _session_lock(self.path):
            if not self.path.exists():
                raise SessionError("فایلی برای بکاپ وجود ندارد")
            data = self.path.read_bytes()
            _atomic_write(backup_path, data)
        return backup_path

    def migrate_to_v2(self, *, backup: bool = True) -> bool:
        """ارتقای هر فرمت قدیمی به ``BKS3`` (AES-GCM + 600k PBKDF2).

        ایمنی:
            - قبل از تبدیل بکاپ گرفته میشود (پیشفرض).
            - ابتدا فایل قدیمی رمزگشایی میشود؛ اگر ناموفق بود، فایل اصلی
              دست نخورده باقی میماند.
            - نوشتن فایل جدید اتمیک است (os.replace).
            - قابلتکرار است: اگر از قبل BKS3 باشد، ``False`` برمیگرداند.
            - Rollback: بکاپ ``<path>.bak`` است؛ ``rollback_migration()``
              آنرا برمیگرداند.

        Returns:
            ``True`` اگر تبدیل انجام شد، ``False`` اگر نیازی نبود.
        """
        # قفل RLock (قابل بازشدن مجدد توسط backup/load_all/save_all) باعث
        # میشود کل توالی migration از سایر عملیات همان process جدا باشد.
        with _session_lock(self.path):
            if not self.path.exists():
                return False
            version = self.format_version(self.path.read_bytes())
            if version == "BKS3":
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
            #    قدیمی قابل تبدیل بماند، بدون اینکه خواندن عادی فایل plain
            #    جعلی را ممکن کند.
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
        with _session_lock(self.path):
            if not backup_path.exists():
                return False
            data = backup_path.read_bytes()

            # تأیید کامل بکاپ قبل از جایگزینی. چک کردن تنها ۶ بایت magic کافی
            # نیست: یک بکاپ با header سالم و بدنه خراب، فایل زنده سالم را با
            # داده غیرقابلخواندن جایگزین میکرد. اینجا بکاپ واقعاً رمزگشایی
            # میشود تا HMAC / GCM tag / JSON هم تأیید شوند.
            probe = SessionStore(backup_path, password=self.password)
            probe.load_all(allow_plain=True)  # در صورت خرابی SessionError — فایل زنده دست نخورده میماند

            _atomic_write(self.path, data)
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
        with _session_lock(self.path):
            # همیشه دیسک را میخوانیم تا نوشته process دیگری دیده شود.
            return self.load_all().get(key)

    def put(self, session: Session) -> str:
        key = self.key_for(session)

        def mutate(sessions: dict[str, Session]) -> str:
            session.touch()
            sessions[key] = session
            return key

        return self._rmw_locked(mutate)

    def delete(self, key: str) -> bool:
        def mutate(sessions: dict[str, Session]) -> bool:
            if key not in sessions:
                return False
            del sessions[key]
            return True

        return self._rmw_locked(mutate)

    def update(self, key: str, updater) -> Session | None:
        """بهروزرسانی اتمیک یک session تحت قفل thread + process.

        برخلاف ``get()`` سپس ``put()`` (که بین آنها قفل آزاد میشود و در
        محیط چندپردازشی Lost Update میدهد)، این متد خواندن، اعمال تغییر و
        نوشتن را بهصورت یک عملیات واحد محافظت میکند.

        Args:
            key: کلید session.
            updater: تابعی که ``Session`` میگیرد و همان/جایگزین را برمیگرداند.

        Returns:
            Session بهروزشده، یا ``None`` اگر کلید وجود نداشت.
        """
        def mutate(sessions: dict[str, Session]) -> Session | None:
            current = sessions.get(key)
            if current is None:
                return None
            updated = updater(current)
            if not isinstance(updated, Session):
                # جلوگیری از ذخیره شدن None/نوع نامعتبر و کرش مبهم حین
                # سریالیزه کردن. فایل سالم باقی میماند چون هنوز نوشته نشده.
                raise SessionError(
                    "updater باید یک Session معتبر برگرداند"
                )
            sessions[key] = updated
            return updated

        return self._rmw_locked(mutate)

    def list_accounts(self) -> list[dict[str, Any]]:
        with _session_lock(self.path):
            sessions = self.load_all()
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
