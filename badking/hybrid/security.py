"""Self Client Security — RBAC، OTP، Session Expiration، Secure Logging.

تمام قابلیتهای امنیتی اینجا متمرکزاند تا قابل تست باشند. هیچ ادعایی بدون
تست مربوطه در `tests/test_self_client_security.py` پذیرفته نمیشود.

قواعد طراحی:
- هیچ شماره تلفن، توکن، transaction_hash یا کد OTP در لاگ چاپ نمیشود.
- مجوزها صریحاند: پیشفرض «اجازه نده» (deny by default).
- انقضای session بر اساس timestamp محلی است، نه سرور (تا جایی که سرور
  اطلاعات دیگری ندهد — این محدودیت صریحاً مستند است).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

# ---------- OTP ----------

_OTP_RE = re.compile(r"^\d{4,8}$")


def validate_otp(code: str) -> str:
    """اعتبارسنجی و نرمالسازی کد OTP.

    فقط ارقام، ۴ تا ۸ رقم. فاصله و خط تیره حذف میشوند.
    """
    if not isinstance(code, str):
        raise ValueError("کد OTP باید رشته باشد")
    cleaned = code.strip().replace(" ", "").replace("-", "")
    if not _OTP_RE.fullmatch(cleaned):
        raise ValueError("کد OTP معتبر نیست (باید ۴ تا ۸ رقم باشد)")
    return cleaned


# ---------- Secure logging ----------

def mask_phone(phone: str) -> str:
    """نمایش امن شماره: فقط ۴ رقم آخر."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) <= 4:
        return "*" * len(digits)
    return "*" * (len(digits) - 4) + digits[-4:]


def mask_token(token: str) -> str:
    """نمایش امن توکن: فقط ۴ رقم/حرف آخر."""
    if not token:
        return ""
    if len(token) <= 4:
        return "*" * len(token)
    return "*" * (len(token) - 4) + token[-4:]


def mask_hash(value: str) -> str:
    """نمایش امن transaction_hash: فقط fingerprint کوتاه."""
    if not value:
        return ""
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()[:8]


def secure_log_context(**kwargs: Any) -> dict[str, str]:
    """تبدیل مقادیر حساس به نسخه قابل لاگ.

    مثال:
        secure_log_context(phone="989123456789", token="abc:xyz")
        → {"phone": "*******6789", "token": "***xyz"}
    """
    out: dict[str, str] = {}
    for key, value in kwargs.items():
        if value is None:
            continue
        text = str(value)
        lower = key.lower()
        if "phone" in lower or "mobile" in lower:
            out[key] = mask_phone(text)
        elif "token" in lower or "secret" in lower or "password" in lower:
            out[key] = mask_token(text)
        elif "hash" in lower or "transaction" in lower:
            out[key] = mask_hash(text)
        elif "code" in lower or "otp" in lower:
            out[key] = "***"
        else:
            out[key] = text
    return out


# ---------- RBAC ----------

# مجوزهای شناختهشده self-bot. پیشفرض: هیچ مجوزی داده نمیشود.
ALL_PERMISSIONS = frozenset({
    "read_messages",
    "send_messages",
    "edit_messages",
    "delete_messages",
    "manage_groups",
    "manage_contacts",
    "media_upload",
    "media_download",
    "raw_rpc",
})

# متدهایی که فقط با مجوز صریح اجرا میشوند (از خطرناکترین به کم خطر)
DANGEROUS_RPCS = frozenset({
    "auth.SignOut",
    "messaging.DeleteMessage",
    "messaging.ClearChat",
    "messaging.DeleteChat",
    "groups.KickUser",
    "groups.LeaveGroup",
    "user.BlockUser",
    "user.ResetContacts",
})

_RPC_PERMISSION = {
    "messaging.SendMessage": "send_messages",
    "messaging.UpdateMessage": "edit_messages",
    "messaging.DeleteMessage": "delete_messages",
    "messaging.LoadHistory": "read_messages",
    "messaging.LoadDialogs": "read_messages",
    "files.GetNasimFileUploadUrl": "media_upload",
    "files.GetNasimFileUrl": "media_download",
    "groups.CreateGroup": "manage_groups",
    "groups.KickUser": "manage_groups",
    "groups.LeaveGroup": "manage_groups",
    "user.AddContact": "manage_contacts",
    "user.BlockUser": "manage_contacts",
}


@dataclass
class PermissionDenied(Exception):
    """خطای مجوز ناکافی."""

    rpc: str
    required: str
    granted: tuple[str, ...]

    def __str__(self) -> str:
        return (
            f"اجرای {self.rpc} نیاز به مجوز '{self.required}' دارد "
            f"(مجوزهای فعلی: {', '.join(self.granted) or 'هیچ'})"
        )


@dataclass
class PermissionPolicy:
    """سیاست مجوز self-bot — deny by default.

    Args:
        allow: مجموعهای از مجوزها. پیشفرض خالی = فقط خواندن پیام مجاز.
        allow_dangerous: اجرای RPCهای خطرناک را صریحاً مجاز میکند.
    """

    allow: frozenset[str] = frozenset()
    allow_dangerous: bool = False

    def __post_init__(self) -> None:
        unknown = set(self.allow) - ALL_PERMISSIONS
        if unknown:
            raise ValueError(f"مجوز ناشناخته: {unknown}")
        self.allow = frozenset(self.allow)

    @classmethod
    def full(cls) -> "PermissionPolicy":
        """همه مجوزها (برای کاربر پیشرفته)."""
        return cls(allow=ALL_PERMISSIONS, allow_dangerous=True)

    def has(self, permission: str) -> bool:
        return permission in self.allow

    def check(self, rpc: str) -> None:
        """بررسی مجوز اجرای RPC. در صورت ناکافی بودن استثنا میدهد."""
        if rpc in DANGEROUS_RPCS and not self.allow_dangerous:
            raise PermissionDenied(rpc, "dangerous", tuple(sorted(self.allow)))
        required = _RPC_PERMISSION.get(rpc)
        if required and required not in self.allow:
            raise PermissionDenied(rpc, required, tuple(sorted(self.allow)))


# ---------- Session expiration ----------

@dataclass
class SessionExpiry:
    """مدت اعتبار session.

    Args:
        max_age_seconds: حداکثر عمر session از آخرین touched.
        absolute_seconds: حداکثر عمر مطلق (حتی با تمدید). None = نامحدود.
    """

    max_age_seconds: float = 30 * 24 * 3600  # ۳۰ روز
    absolute_seconds: float | None = None
    _created: float = field(default_factory=time.time, repr=False)

    def is_expired(self, touched_at: float | None, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        if self.absolute_seconds is not None:
            if now - self._created > self.absolute_seconds:
                return True
        if touched_at is None:
            return True
        return (now - touched_at) > self.max_age_seconds

    def remaining(self, touched_at: float | None, now: float | None = None) -> float:
        now = now if now is not None else time.time()
        if touched_at is None:
            return 0.0
        return max(0.0, self.max_age_seconds - (now - touched_at))


# ---------- Authentication error mapping ----------

_AUTH_ERROR_HINTS = {
    400: "درخواست نامعتبر — کد یا شماره را بررسی کن",
    401: "احراز هویت ناموفق — ممکن است نیاز به ورود مجدد باشد",
    403: "دسترسی رد شد",
    429: "تعداد درخواستها زیاد است — صبر کن",
}


def auth_error_hint(code: int) -> str:
    """پیام قابل فهم برای کد خطای احراز هویت."""
    return _AUTH_ERROR_HINTS.get(code, "خطای احراز هویت")


def constant_time_equals(a: str, b: str) -> bool:
    """مقایسه امن توکن/HMAC بدون timing leak."""
    return hmac.compare_digest(a.encode(), b.encode())
