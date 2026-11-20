"""احراز هویت self-bot: شماره تلفن + کد SMS.

جریان کار:
    1. `request_code(phone)` → سرور کد SMS می‌فرستد، یک transaction_hash برمی‌گردد
    2. `sign_in(transaction_hash, code)` → access_token (JWT)
    3. session ذخیره می‌شود؛ دفعه بعد بدون کد وصل می‌شوی

هشدار: این endpoint ها بخشی از API عمومی بله نیستند. اگر بله تغییرشان دهد،
این ماژول می‌شکند. هرگز شماره اصلی‌ات را استفاده نکن.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from .jwt_verify import JWTVerifier, JWTVerificationFailed
from .proto import build, decode, get_int, get_str
from .security import (
    OTPAlreadyUsed,
    OTPAttemptLimitExceeded,
    OTPExpired,
    OTPGuard,
    mask_phone,
    secure_log_context,
    validate_otp,
)
from .session import Session

logger = logging.getLogger("badking.hybrid.auth")

# ---------- endpoint ها ----------
# این‌ها از کلاینت وب بله استخراج شده‌اند. با env قابل override هستند تا اگر
# بله آدرس را عوض کرد، بدون انتشار نسخه جدید بتوانی وصل شوی.
DEFAULT_REST_BASE = os.environ.get(
    "BADKING_BALE_REST", "https://next-ws.bale.ai"
)
DEFAULT_WS_URL = os.environ.get(
    "BADKING_BALE_WS", "wss://next-ws.bale.ai/ws"
)

# ---------- شماره فیلدها ----------
# چون .proto رسمی نیست، شماره فیلدها اینجا متمرکز است. اگر پروتکل عوض شد،
# فقط این جدول را عوض کن.
F_PHONE = 1
F_TRANSACTION_HASH = 2
F_CODE = 3
F_ACCESS_TOKEN = 4
F_REFRESH_TOKEN = 5
F_USER_ID = 6
F_NAME = 7
F_USERNAME = 8
F_DEVICE_MODEL = 9
F_APP_VERSION = 10
F_ERROR_CODE = 15
F_ERROR_MESSAGE = 16
F_RETRY_AFTER = 17


class AuthError(Exception):
    """خطای احراز هویت."""

    def __init__(self, message: str, code: int = 0, retry_after: float | None = None):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


@dataclass
class CodeRequest:
    """نتیجه درخواست کد SMS."""

    transaction_hash: str
    phone: str
    is_registered: bool = True
    retry_after: float | None = None


@dataclass
class SignInResult:
    """نتیجه ورود موفق."""

    session: Session
    is_new_user: bool = False


def normalize_phone(phone: str) -> str:
    """نرمال‌سازی شماره به فرمت بین‌المللی بدون +.

    '09123456789' → '989123456789'
    '+98 912 345 6789' → '989123456789'
    """
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not digits:
        raise AuthError("شماره تلفن خالی است")
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = "98" + digits[1:]
    elif not digits.startswith("98") and len(digits) == 10:
        digits = "98" + digits
    if len(digits) < 10:
        raise AuthError(f"شماره تلفن معتبر نیست: {phone}")
    return digits


def device_fingerprint(phone: str) -> dict[str, str]:
    """اثر انگشت دستگاه پایدار برای هر شماره.

    بله دستگاه‌ها را می‌شناسد؛ اگر هر بار اثر انگشت عوض شود، ممکن است
    ورود مشکوک تلقی شود. این تابع یک اثر انگشت ثابت از شماره می‌سازد.
    """
    seed = hashlib.sha256(f"badking:{phone}".encode()).hexdigest()
    return {
        "device_model": f"BADKING-{seed[:6].upper()}",
        "app_version": "1.0.0",
        "device_hash": seed[:32],
    }


class AuthFlow:
    """جریان احراز هویت روی یک transport."""

    def __init__(
        self,
        transport: Any,
        rest_base: str = DEFAULT_REST_BASE,
        otp_guard: OTPGuard | None = None,
        jwt_verifier: JWTVerifier | None = None,
    ):
        """جریان احراز هویت.

        Args:
            transport: transportای که RPCهای auth روی آن ارسال میشود.
            otp_guard: در صورت تنظیم، چالشهای OTP با محدودیت تلاش، انقضا
                و جلوگیری از replay محافظت میشوند. پیشفرض None (رفتار قدیمی).
            jwt_verifier: در صورت تنظیم، توکنهای access/refresh واقعاً
                verify میشوند. پیشفرض None (وضعیت NOT_VERIFIED — صریحاً
                مستند است؛ بله کلید عمومی نمیدهد).
        """
        self.transport = transport
        self.rest_base = rest_base.rstrip("/")
        self.otp_guard = otp_guard
        self.jwt_verifier = jwt_verifier

    async def request_code(self, phone: str) -> CodeRequest:
        """درخواست کد SMS برای شماره."""
        normalized = normalize_phone(phone)
        fp = device_fingerprint(normalized)
        payload = build(
            {
                F_PHONE: normalized,
                F_DEVICE_MODEL: fp["device_model"],
                F_APP_VERSION: fp["app_version"],
            }
        )
        frame = await self.transport.request(payload)
        msg = decode(frame)
        _raise_if_error(msg)

        tx = get_str(msg, F_TRANSACTION_HASH)
        if not tx:
            raise AuthError("سرور transaction_hash برنگرداند")
        retry = get_int(msg, F_RETRY_AFTER) or None
        # چالش OTP فقط وقتی guard فعال است صادر میشود. کد واقعی نزد ما
        # وجود ندارد (سرور آنرا پیامک میکند) — بنابراین guard فقط شمارش
        # تلاشها، انقضا و replay را روی هش کدی که کاربر وارد میکند اعمال
        # میکند. در sign_in چالش با همان کد واردشده «صادر» و سپس verify
        # میشود تا replay دفعات بعدیگرفته شود.
        logger.info("کد SMS ارسال شد به %s", mask_phone(normalized))
        return CodeRequest(
            transaction_hash=tx,
            phone=normalized,
            is_registered=bool(get_int(msg, F_USER_ID, 1)),
            retry_after=float(retry) if retry else None,
        )

    async def sign_in(self, transaction_hash: str, code: str, phone: str = "") -> SignInResult:
        """تأیید کد و دریافت access_token."""
        try:
            code = validate_otp(code)
        except ValueError as exc:
            raise AuthError(str(exc)) from exc

        if self.otp_guard is not None:
            self._enforce_otp(transaction_hash)

        payload = build({F_TRANSACTION_HASH: transaction_hash, F_CODE: code})
        frame = await self.transport.request(payload)
        msg = decode(frame)
        _raise_if_error(msg)

        token = get_str(msg, F_ACCESS_TOKEN)
        if not token:
            raise AuthError("سرور access_token برنگرداند (کد اشتباه؟)")
        self._verify_token(token)

        session = Session(
            access_token=token,
            refresh_token=get_str(msg, F_REFRESH_TOKEN),
            user_id=get_int(msg, F_USER_ID) or None,
            phone=normalize_phone(phone) if phone else "",
            name=get_str(msg, F_NAME),
            username=get_str(msg, F_USERNAME),
        )
        is_new = not bool(get_int(msg, F_USER_ID))
        if self.otp_guard is not None:
            # سرور کد را تأیید کرد — چالش را مصرفشده علامت میزنیم تا
            # replay جلوگیری شود. transaction تازه مستقل است.
            self.otp_guard.mark_used(transaction_hash)
        logger.info("ورود موفق: user_id=%s", session.user_id)
        return SignInResult(session=session, is_new_user=is_new)

    def _enforce_otp(self, challenge_id: str) -> None:
        """اعمال محدودیت تلاش/انقضا/replay قبل از ارسال به سرور.

        کد OTP واقعی را سرور پیامک میکند و نزد ما نیست، بنابراین صحت آنرا
        نمیتوانیم محلی بررسی کنیم. OTPGuard در حالت «blind» فقط:
          - تعداد تلاشها را محدود میکند (Brute Force)
          - TTL چالش را رعایت میکند (Expiration)
          - چالش مصرفشده را رد میکند (Replay)
        صحت نهایی کد توسط سرور تعیین میشود — هیچ ادعای محلیای نمیشود.
        """
        guard = self.otp_guard
        assert guard is not None
        try:
            guard.check_blind(challenge_id)
        except OTPAlreadyUsed as exc:
            raise AuthError("کد تأیید قبلاً استفاده شده است") from exc
        except OTPExpired as exc:
            raise AuthError("کد تأیید منقضی شده است") from exc
        except OTPAttemptLimitExceeded as exc:
            raise AuthError("تعداد تلاشهای کد تأیید بیش از حد مجاز است") from exc

    def _verify_token(self, token: str) -> None:
        """اعمال JWT verification واقعی در مسیر مصرف توکن."""
        if self.jwt_verifier is None:
            return
        try:
            self.jwt_verifier.verify(token)
        except JWTVerificationFailed as exc:
            raise AuthError("توکن دسترسی نامعتبر است") from exc

    async def refresh(self, session: Session) -> Session:
        """تمدید توکن با refresh_token."""
        if not session.refresh_token:
            raise AuthError("refresh_token نداریم؛ دوباره با کد SMS وارد شو")
        payload = build({F_REFRESH_TOKEN: session.refresh_token})
        frame = await self.transport.request(payload)
        msg = decode(frame)
        _raise_if_error(msg)
        token = get_str(msg, F_ACCESS_TOKEN)
        if not token:
            raise AuthError("تمدید توکن ناموفق بود")
        self._verify_token(token)
        session.access_token = token
        new_refresh = get_str(msg, F_REFRESH_TOKEN)
        if new_refresh:
            session.refresh_token = new_refresh
        session.touch()
        return session


def _raise_if_error(msg: dict[int, list[Any]]) -> None:
    """اگر پیام خطا داشت، استثنا بنداز."""
    code = get_int(msg, F_ERROR_CODE)
    if not code:
        return
    message = get_str(msg, F_ERROR_MESSAGE) or f"خطای سرور (کد {code})"
    retry = get_int(msg, F_RETRY_AFTER) or None
    raise AuthError(message, code=code, retry_after=float(retry) if retry else None)


async def interactive_login(
    transport_factory: Any,
    phone: str,
    store: Any,
    code_prompt: Any = None,
) -> Session:
    """ورود تعاملی: شماره، کد، ذخیره session.

    `code_prompt` یک تابع است که کد را از کاربر می‌گیرد. پیش‌فرض input().
    """
    if code_prompt is None:
        code_prompt = input

    transport = transport_factory()
    await transport.connect()
    try:
        flow = AuthFlow(transport)
        req = await flow.request_code(phone)
        if req.retry_after:
            logger.info("صبر کن %.0f ثانیه", req.retry_after)
            await asyncio.sleep(req.retry_after)
        code = await asyncio.get_event_loop().run_in_executor(
            None, code_prompt, "کد تأیید SMS: "
        )
        result = await flow.sign_in(req.transaction_hash, code, phone=req.phone)
        store.put(result.session)
        return result.session
    finally:
        await transport.close()
