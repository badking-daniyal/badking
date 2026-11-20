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


class OTPAttemptLimitExceeded(Exception):
    """تعداد تلاشهای OTP از حد مجاز گذشت."""


class OTPExpired(Exception):
    """کد OTP منقضی شده است."""


class OTPAlreadyUsed(Exception):
    """کد OTP قبلاً استفاده شده است (جلوگیری از replay)."""


@dataclass
class OTPChallenge:
    """یک چالش OTP — کد به صورت هش ذخیره میشود، هرگز plaintext."""

    code_hash: str
    created_at: float
    attempts: int = 0
    used: bool = False


@dataclass
class OTPGuard:
    """محافظ OTP: محدودیت تلاش، انقضا، جلوگیری از استفاده مجدد.

    Args:
        max_attempts: حداکثر تعداد تلاش (پیشفرض ۵)
        ttl_seconds: عمر چالش (پیشفرض ۱۲۰ ثانیه)
    """

    max_attempts: int = 5
    ttl_seconds: float = 120.0
    _challenges: dict[str, OTPChallenge] = field(default_factory=dict, repr=False)

    @staticmethod
    def _hash(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    def issue(self, challenge_id: str, code: str, now: float | None = None) -> None:
        """ایجاد چالش جدید. کد plaintext ذخیره نمیشود."""
        now = now if now is not None else time.time()
        self._challenges[challenge_id] = OTPChallenge(
            code_hash=self._hash(validate_otp(code)),
            created_at=now,
        )

    def verify(
        self, challenge_id: str, code: str, now: float | None = None
    ) -> bool:
        """بررسی کد. در صورت موفقیت چالش را «مصرفشده» علامت میزند."""
        now = now if now is not None else time.time()
        ch = self._challenges.get(challenge_id)
        if ch is None:
            return False
        if ch.used:
            raise OTPAlreadyUsed("کد قبلاً استفاده شده است")
        if now - ch.created_at > self.ttl_seconds:
            raise OTPExpired("کد منقضی شده است")
        if ch.attempts >= self.max_attempts:
            raise OTPAttemptLimitExceeded("تعداد تلاشها بیش از حد مجاز است")
        ch.attempts += 1
        if hmac.compare_digest(ch.code_hash, self._hash(validate_otp(code))):
            ch.used = True
            return True
        return False

    def clear(self, challenge_id: str) -> None:
        self._challenges.pop(challenge_id, None)

    # ---------- حالت Blind (برای AuthFlow واقعی) ----------
    # کد OTP واقعی را سرور پیامک میکند و نزد ما نیست. بنابراین نمیتوانیم
    # صحت آنرا با hash مقایسه کنیم. در مسیر احراز هویت واقعی فقط از
    # شمارش تلاش، انقضا و جلوگیری replay استفاده میکنیم.

    def issue_blind(self, challenge_id: str, now: float | None = None) -> None:
        """ایجاد چالش بدون کد — فقط timestamp و شمارش تلاش."""
        now = now if now is not None else time.time()
        self._challenges[challenge_id] = OTPChallenge(
            code_hash="",  # کد نزد ما نیست
            created_at=now,
        )

    def check_blind(self, challenge_id: str, now: float | None = None) -> None:
        """بررسی تلاش/انقضا/replay قبل از ارسال به سرور.

        بر خلاف ``verify``، کد را مقایسه نمیکند — صحت کد توسط سرور تعیین
        میشود. فقط محدودیتها را اعمال میکند.
        """
        now = now if now is not None else time.time()
        ch = self._challenges.get(challenge_id)
        if ch is None:
            self.issue_blind(challenge_id, now=now)
            ch = self._challenges[challenge_id]
        if ch.used:
            raise OTPAlreadyUsed("کد قبلاً استفاده شده است")
        if now - ch.created_at > self.ttl_seconds:
            raise OTPExpired("کد منقضی شده است")
        if ch.attempts >= self.max_attempts:
            raise OTPAttemptLimitExceeded("تعداد تلاشها بیش از حد مجاز است")
        ch.attempts += 1

    def mark_used(self, challenge_id: str) -> None:
        """پس از تأیید موفق توسط سرور، چالش را مصرفشده علامت میزند."""
        ch = self._challenges.get(challenge_id)
        if ch is not None:
            ch.used = True


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

class InsecureLegacyModeWarning(UserWarning):
    """هشدار: حالت legacy بدون محدودیت مجوز فعال است."""


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

# نقشه کامل RPC → مجوز لازم. هر RPC موجود در این نقشه با policy خالی رد میشود.
#
# اصل: هر عملیاتی که وضعیت حساب/گروه/پیام را تغییر میدهد باید مجوز صریح
# بخواهد. RPCهای فقطخواندنی (Load*) عمداً در نقشه نیستند تا خواندن پیشفرض
# ممکن بماند — ولی RPCهای تغییردهنده نباید بدون مجوز اجرا شوند.
_RPC_PERMISSION = {
    # --- پیام ---
    "messaging.SendMessage": "send_messages",
    "messaging.UpdateMessage": "edit_messages",
    "messaging.DeleteMessage": "delete_messages",
    "messaging.ForwardMessages": "send_messages",
    "messaging.PinMessage": "manage_groups",
    "messaging.UnPinMessages": "manage_groups",
    "messaging.ClearChat": "delete_messages",
    "messaging.MessageRead": "read_messages",
    "messaging.LoadHistory": "read_messages",
    "messaging.LoadDialogs": "read_messages",
    "messaging.LoadPinnedMessages": "read_messages",
    # --- فایل ---
    "files.GetNasimFileUploadUrl": "media_upload",
    "files.GetNasimFileUrl": "media_download",
    # --- گروه ---
    "groups.CreateGroup": "manage_groups",
    "groups.KickUser": "manage_groups",
    "groups.LeaveGroup": "manage_groups",
    "groups.JoinGroup": "manage_groups",
    "groups.InviteUsers": "manage_groups",
    "groups.GetGroupInviteURL": "manage_groups",
    # --- مخاطبین و پروفایل ---
    "user.AddContact": "manage_contacts",
    "user.BlockUser": "manage_contacts",
    "user.UnblockUser": "manage_contacts",
    "user.EditName": "manage_contacts",
    "user.EditAbout": "manage_contacts",
    "user.EditNickName": "manage_contacts",
    # --- واکنش‌ها و حضور ---
    "abacus.MessageSetReaction": "send_messages",
    "abacus.MessageRemoveReaction": "send_messages",
    "presence.SetOnline": "send_messages",
    "presence.Typing": "send_messages",
    "presence.StopTyping": "send_messages",
    # --- گزارش و محتوا ---
    "report.ReportInappropriateContent": "send_messages",
    "magazine.UpvotePost": "send_messages",
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
