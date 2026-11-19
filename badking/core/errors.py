"""خطاهای BADKING — سلسله‌مراتب کامل، با راه‌حل پیشنهادی.

بزرگ‌ترین شکایت توسعه‌دهنده‌ها از کتابخانه‌های موجود: خطای نامفهوم. پیام
`KeyError: 'result'` به کسی نمی‌گوید چه کار کند.

قانون این فایل: هر خطا سه چیز دارد — **چه شد**، **چرا**، و **چه کار کن**.
اگر خطایی راه‌حل ندارد، یعنی نباید وجود داشته باشد.

    from badking import BADKINGError, AuthenticationError

    try:
        await bot.send_message(peer, "سلام")
    except RateLimitError as exc:
        print(exc.retry_after)   # چند ثانیه صبر کن
    except BADKINGError as exc:
        print(exc.diagnose())    # گزارش کامل، آماده برای Issue
"""

from __future__ import annotations

import traceback
from typing import Any


# ---------- پایه ----------

class BADKINGError(Exception):
    """ریشه همه خطاهای BADKING.

    هر خطا `code`، `method`، و `hint` دارد. `hint` جمله‌ای است که مستقیماً
    می‌گوید چه کار کنی — نه توضیح فنی، دستور عمل.
    """

    #: کد یکتای خطا برای مستندات و جستجو
    error_code: str = "BADKING_ERROR"
    #: راه‌حل پیش‌فرض
    default_hint: str = ""

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        description: str | None = None,
        parameters: dict[str, Any] | None = None,
        method: str | None = None,
        hint: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.description = description
        self.parameters = parameters or {}
        self.method = method
        self.hint = hint or self.default_hint
        self.cause = cause

    # ---------- کمکی ----------

    @property
    def retry_after(self) -> float | None:
        """چند ثانیه صبر کن. فقط برای RateLimitError معنا دارد."""
        value = self.parameters.get("retry_after")
        return float(value) if value is not None else None

    @property
    def retryable(self) -> bool:
        """آیا تلاش مجدد منطقی است؟"""
        return False

    def diagnose(self) -> str:
        """گزارش کامل برای Issue یا لاگ. اطلاعات حساس حذف می‌شود."""
        lines = [
            f"{type(self).__name__}: {self.message}",
            f"  error_code: {self.error_code}",
        ]
        if self.code is not None:
            lines.append(f"  server_code: {self.code}")
        if self.method:
            lines.append(f"  method: {self.method}")
        if self.hint:
            lines.append(f"  راه‌حل: {self.hint}")
        if self.cause is not None:
            lines.append(f"  علت: {type(self.cause).__name__}: {self.cause}")
        return "\n".join(lines)

    def __str__(self) -> str:
        base = self.message
        if self.method:
            base = f"[{self.method}] {base}"
        if self.hint:
            base = f"{base}\n  → {self.hint}"
        return base

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.message!r}, code={self.code!r})"


# ---------- احراز هویت ----------

class AuthenticationError(BADKINGError):
    """احراز هویت شکست خورد."""

    error_code = "AUTH_FAILED"
    default_hint = "توکن یا نشست را بررسی کن. برای ربات: توکن @botfather. برای self-bot: دوباره login کن."


class UnauthorizedError(AuthenticationError):
    """توکن نامعتبر یا منقضی (error_code 401)."""

    error_code = "UNAUTHORIZED"
    default_hint = "توکن اشتباه است یا باطل شده. یک توکن تازه از @botfather بگیر."


class SessionError(BADKINGError):
    """نشست self-bot خراب، منقضی، یا قابل خواندن نیست."""

    error_code = "SESSION_INVALID"
    default_hint = "فایل نشست را پاک کن و دوباره `badking login` بزن."


class SessionExpiredError(SessionError):
    """نشست منقضی شده و باید تازه شود."""

    error_code = "SESSION_EXPIRED"
    default_hint = "نشست منقضی شده. دوباره login کن."


class CodeInvalidError(AuthenticationError):
    """کد تأیید SMS اشتباه است."""

    error_code = "CODE_INVALID"
    default_hint = "کد را دوباره وارد کن. اگر چند بار اشتباه شد، کمی صبر کن."


class PasswordNeededError(AuthenticationError):
    """حساب رمز دومرحله‌ای دارد."""

    error_code = "PASSWORD_NEEDED"
    default_hint = "این حساب رمز دارد. با password= آن را بده."


# ---------- اتصال ----------

class ConnectionError(BADKINGError):
    """اتصال برقرار نشد یا قطع شد."""

    error_code = "CONNECTION_FAILED"
    default_hint = "اینترنت و آدرس سرور را بررسی کن. اگر پشت پروکسی هستی، proxy= را تنظیم کن."

    @property
    def retryable(self) -> bool:
        return True


class ConnectionLostError(ConnectionError):
    """اتصال وسط کار قطع شد."""

    error_code = "CONNECTION_LOST"
    default_hint = "اتصال قطع شد. auto_reconnect=True معمولاً خودش وصل می‌کند."

    @property
    def retryable(self) -> bool:
        return True


class TimeoutError_(BADKINGError):
    """درخواست در زمان مجاز پاسخ نداد."""

    error_code = "TIMEOUT"
    default_hint = "timeout= را بیشتر کن، یا شبکه را بررسی کن."

    @property
    def retryable(self) -> bool:
        return True


class NetworkError(ConnectionError):
    """خطای شبکه: DNS، SSL، یا قطعی اینترنت."""

    error_code = "NETWORK_ERROR"
    default_hint = "DNS یا SSL را بررسی کن. اگر در ایران هستی، ممکن است فیلتر علت باشد."

    @property
    def retryable(self) -> bool:
        return True


class DnsError(NetworkError):
    """نام دامنه حل نشد."""

    error_code = "DNS_FAILED"
    default_hint = "دامنه حل نمی‌شود. DNS سیستم یا VPN را بررسی کن."


class TlsError(NetworkError):
    """گواهی SSL معتبر نبود."""

    error_code = "TLS_FAILED"
    default_hint = "گواهی SSL رد شد. ساعت سیستم را بررسی کن؛ اگر درست بود، به MITM شک کن."


# ---------- نرخ و محدودیت ----------

class RateLimitError(BADKINGError):
    """محدودیت نرخ سرور (error_code 429)."""

    error_code = "RATE_LIMITED"
    default_hint = "کمی صبر کن. `retry_after` می‌گوید چند ثانیه."

    @property
    def retryable(self) -> bool:
        return True


class FloodWaitError(RateLimitError):
    """سرور صریحاً می‌گوید چند ثانیه صبر کن."""

    error_code = "FLOOD_WAIT"
    default_hint = "سرور گفته صبر کن. `await asyncio.sleep(exc.retry_after)`."


class CircuitOpenError(BADKINGError):
    """مدارشکن باز است: سرور پیاپی خطا داده، درخواست فرستاده نشد."""

    error_code = "CIRCUIT_OPEN"
    default_hint = "سرور مدتی خطا داده. CircuitBreaker خودش بعد از cooldown تست می‌کند."

    @property
    def retryable(self) -> bool:
        return True


# ---------- مجوز ----------

class PermissionError_(BADKINGError):
    """اجازه این کار را نداری."""

    error_code = "PERMISSION_DENIED"
    default_hint = "ربات باید ادمین باشد، یا تو باید مالک گروه باشی."


class NotAdminError(PermissionError_):
    """کاربر یا ربات ادمین نیست."""

    error_code = "NOT_ADMIN"
    default_hint = "اول ربات را ادمین کن، یا از مالک گروه بخواه."


class ChatNotFoundError(BADKINGError):
    """چت پیدا نشد."""

    error_code = "CHAT_NOT_FOUND"
    default_hint = "شناسه چت یا یوزرنیم را بررسی کن. ربات باید قبلاً آن چت را دیده باشد."


class UserNotFoundError(BADKINGError):
    """کاربر پیدا نشد."""

    error_code = "USER_NOT_FOUND"
    default_hint = "شناسه یا یوزرنیم کاربر را بررسی کن."


# ---------- پیام ----------

class MessageError(BADKINGError):
    """خطای مربوط به پیام."""

    error_code = "MESSAGE_ERROR"
    default_hint = "محتوای پیام و شناسه چت را بررسی کن."


class MessageTooLongError(MessageError):
    """متن از حد مجاز بلندتر است."""

    error_code = "MESSAGE_TOO_LONG"
    default_hint = "از smart_split_text() استفاده کن تا خودکار بشکند."


class MessageNotFoundError(MessageError):
    """پیام با این شناسه نیست — حذف شده یا شناسه غلط است."""

    error_code = "MESSAGE_NOT_FOUND"
    default_hint = "شناسه پیام را بررسی کن. پیام حذف‌شده قابل بازیابی نیست."


class ChatWriteForbiddenError(MessageError):
    """اجازه نوشتن در این چت نیست."""

    error_code = "CHAT_WRITE_FORBIDDEN"
    default_hint = "ربات عضو نیست، یا ارسال در گروه بسته شده."


class ReplyNotFoundError(MessageError):
    """پیامی که می‌خواهی به آن پاسخ دهی نیست."""

    error_code = "REPLY_NOT_FOUND"
    default_hint = "پیام مرجع حذف شده. reply_to را بردار."


# ---------- رسانه ----------

class MediaError(BADKINGError):
    """خطای آپلود یا دانلود."""

    error_code = "MEDIA_ERROR"
    default_hint = "فایل و نوع MIME را بررسی کن."


class FileTooLargeError(MediaError):
    """حجم فایل از حد مجاز بیشتر است."""

    error_code = "FILE_TOO_LARGE"
    default_hint = "فایل را فشرده کن یا به قطعات بشکن."


class UnsupportedMediaError(MediaError):
    """این نوع فایل پشتیبانی نمی‌شود."""

    error_code = "UNSUPPORTED_MEDIA"
    default_hint = "نوع فایل را به یکی از انواع مجاز بله تبدیل کن."


class UploadFailedError(MediaError):
    """آپلود نیمه‌کاره ماند."""

    error_code = "UPLOAD_FAILED"
    default_hint = "دوباره تلاش کن. اگر تکرار شد، حجم و شبکه را بررسی کن."

    @property
    def retryable(self) -> bool:
        return True


class DownloadFailedError(MediaError):
    """دانلود شکست خورد."""

    error_code = "DOWNLOAD_FAILED"
    default_hint = "لینک فایل منقضی شده. پیام را دوباره بخوان تا لینک تازه بگیری."

    @property
    def retryable(self) -> bool:
        return True


# ---------- اعتبارسنجی ----------

class ValidationError(BADKINGError):
    """ورودی نامعتبر است."""

    error_code = "VALIDATION_FAILED"
    default_hint = "نوع و مقدار پارامترها را بررسی کن."


class MissingParameterError(ValidationError):
    """پارامتر لازم داده نشده."""

    error_code = "MISSING_PARAMETER"
    default_hint = "پارامتر لازم را پاس بده."


class InvalidPeerError(ValidationError):
    """شناسه چت قابل تفسیر نیست."""

    error_code = "INVALID_PEER"
    default_hint = "از make_peer() یا شناسه عددی استفاده کن، نه رشته دلخواه."


# ---------- پروتکل ----------

class ProtocolError(BADKINGError):
    """خطای سطح پروتکل: فریم نامعتبر، اسکیمای ناشناخته."""

    error_code = "PROTOCOL_ERROR"
    default_hint = "ممکن است بله پروتکل را عوض کرده باشد. BADKING_RPC_SCHEMA را به‌روز کن."


class DecodeError(ProtocolError):
    """پاسخ سرور قابل رمزگشایی نبود."""

    error_code = "DECODE_FAILED"
    default_hint = "اسکیمای پاسخ برای این متد اشتباه است. با `badking rpc --describe` بررسی کن."


class EncodeError(ProtocolError):
    """درخواست قابل کدگذاری نبود."""

    error_code = "ENCODE_FAILED"
    default_hint = "فیلدها با اسکیما نمی‌خوانند. `badking rpc --describe <method>` را ببین."


class UnknownMethodError(ProtocolError):
    """این RPC در رجیستری نیست."""

    error_code = "UNKNOWN_METHOD"
    default_hint = "نام متد را بررسی کن، یا با raw_call() و شماره فیلد خام صدایش بزن."


class RpcFailedError(ProtocolError):
    """سرور به RPC پاسخ خطا داد."""

    error_code = "RPC_FAILED"
    default_hint = "پیام سرور را بخوان؛ معمولاً می‌گوید کدام فیلد مشکل دارد."


# ---------- ذخیره‌سازی ----------

class StorageError(BADKINGError):
    """خطای دیتابیس یا ذخیره‌سازی."""

    error_code = "STORAGE_ERROR"
    default_hint = "مسیر فایل و مجوز نوشتن را بررسی کن."


class StorageLockedError(StorageError):
    """دیتابیس قفل است — پروسه دیگری دارد می‌نویسد."""

    error_code = "STORAGE_LOCKED"
    default_hint = "SQLite یک نویسنده هم‌زمان می‌پذیرد. صف بنویس یا به PostgreSQL برو."

    @property
    def retryable(self) -> bool:
        return True


# ---------- پیکربندی ----------

class ConfigError(BADKINGError):
    """پیکربندی ناقص یا نامعتبر."""

    error_code = "CONFIG_INVALID"
    default_hint = "فایل تنظیمات را بررسی کن. `badking doctor` می‌گوید چه چیزی کم است."


class MissingTokenError(ConfigError):
    """توکن داده نشده."""

    error_code = "MISSING_TOKEN"
    default_hint = "توکن را از @botfather بگیر و به Bot() بده یا در .env بگذار."


# ---------- نام‌های قدیمی (سازگاری) ----------

#: نام قدیمی ریشه خطاها. از BADKINGError استفاده کن.
BaleError = BADKINGError


class StopPropagation(Exception):
    """جلوگیری از اجرای هندلرهای بعدی.

    عمداً از BADKINGError ارث نمی‌برد: خطا نیست، کنترل جریان است.
    """


class BadRequestError(ValidationError):
    """نام قدیمی. از ValidationError استفاده کن."""

    error_code = "BAD_REQUEST"


# ---------- نگاشت کد سرور ----------

ERROR_CLASSES: dict[int, type[BADKINGError]] = {
    400: ValidationError,
    401: UnauthorizedError,
    403: PermissionError_,
    404: ChatNotFoundError,
    420: FloodWaitError,
    429: RateLimitError,
    500: BADKINGError,
    502: BADKINGError,
    503: BADKINGError,
}


def error_for_code(code: int | None) -> type[BADKINGError]:
    """کلاس مناسب برای کد خطای سرور."""
    if code is None:
        return BADKINGError
    return ERROR_CLASSES.get(code, BADKINGError)


def raise_for_response(data: dict[str, Any], method: str | None = None) -> Any:
    """پاسخ API بله را بررسی و در صورت خطا exception پرتاب می‌کند."""
    if data.get("ok") is True:
        return data.get("result")

    code = data.get("error_code")
    desc = data.get("description") or "خطای نامشخص از سرور بله"
    params = data.get("parameters") or {}
    cls = error_for_code(code)

    # پیام‌های پرتکرار سرور، راه‌حل اختصاصی می‌گیرند
    hint = None
    low = desc.lower()
    if "flood" in low or "too many" in low:
        cls = FloodWaitError
    elif "not enough rights" in low or "admin" in low:
        cls = NotAdminError
    elif "chat not found" in low:
        cls = ChatNotFoundError
    elif "message is too long" in low:
        cls = MessageTooLongError
    elif "message to reply not found" in low:
        cls = ReplyNotFoundError
    elif "bot was blocked" in low:
        cls = ChatWriteForbiddenError
        hint = "کاربر ربات را بلاک کرده. تا آنبلاک نکند نمی‌توانی پیام بدهی."

    raise cls(
        f"{desc} (code={code})",
        code=code,
        description=desc,
        parameters=params,
        method=method,
        hint=hint,
    )


# ---------- ابزار عیب‌یابی ----------

def format_exception(exc: BaseException, *, include_traceback: bool = False) -> str:
    """خطا را خوانا چاپ می‌کند، بدون افشای توکن.

    توکن‌های شبیه `123456:ABC-DEF...` و کلیدهای بلند هگز خودکار پاک می‌شوند.
    """
    import re

    if isinstance(exc, BADKINGError):
        text = exc.diagnose()
    else:
        text = f"{type(exc).__name__}: {exc}"

    if include_traceback:
        text += "\n\n" + "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )

    # پاک‌سازی توکن و کلید
    text = re.sub(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", "<TOKEN>", text)
    text = re.sub(r"\b[A-Fa-f0-9]{32,}\b", "<HEX_SECRET>", text)
    return text


__all__ = [
    "AuthenticationError",
    "BADKINGError",
    "BadRequestError",
    "BaleError",
    "ChatNotFoundError",
    "ChatWriteForbiddenError",
    "CircuitOpenError",
    "CodeInvalidError",
    "ConfigError",
    "ConnectionError",
    "ConnectionLostError",
    "DecodeError",
    "DnsError",
    "DownloadFailedError",
    "EncodeError",
    "ERROR_CLASSES",
    "FileTooLargeError",
    "FloodWaitError",
    "InvalidPeerError",
    "MediaError",
    "MessageError",
    "MessageNotFoundError",
    "MessageTooLongError",
    "MissingParameterError",
    "MissingTokenError",
    "NetworkError",
    "NotAdminError",
    "PasswordNeededError",
    "PermissionError_",
    "ProtocolError",
    "RateLimitError",
    "ReplyNotFoundError",
    "RpcFailedError",
    "SessionError",
    "SessionExpiredError",
    "StorageError",
    "StopPropagation",
    "StorageLockedError",
    "TimeoutError_",
    "TlsError",
    "UnauthorizedError",
    "UnknownMethodError",
    "UnsupportedMediaError",
    "UploadFailedError",
    "UserNotFoundError",
    "ValidationError",
    "error_for_code",
    "format_exception",
    "raise_for_response",
]
