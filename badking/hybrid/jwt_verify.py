"""JWT verification امن و واقعی برای self-bot.

چرا opt-in است؟
    بله توکنهایش را با کلید سرور امضا میکند و آن کلید عمومی در اختیار ما
    نیست. بنابراین نمیتوانیم امضای توکن واقعی بله را تأیید کنیم. این ماژول
    وقتی فعال است که کاربر صریحاً کلید (یا secret) را بدهد — مثلاً وقتی
    BADKING به عنوان سرویس احراز هویت próprio استفاده میشود، یا وقتی کلید
    سرور را از منبع معتبر دارد.

    وقتی کلیدی داده نشود، verification انجام نمیشود و وضعیت صریحاً
    ``NOT_VERIFIED`` است. هیچ ادعای امنیتی غیرواقعیای نمیشود.

وقتی فعال است، چه چیزهایی بررسی میشود؟
    - امضای واقعی (PyJWT، الگوریتمهای صریح محدود)
    - جلوگیری از Algorithm Confusion (الگوریتم از هدر توکن خوانده نمیشود)
    - رد الگوریتم ``none``
    - exp / nbf / iat (با تحمل قابلتنظیم leeway)
    - issuer و audience در صورت پیکربندی
    - توکن malformed / ساختار نامعتبر
    - خطاهای امن و بدون نشت توکن

وابستگی: PyJWT (MIT license)، سازگار با Python 3.9–3.12.
رمزنگاری دستساز در اینجا وجود ندارد — semua کارها توسط PyJWT انجام میشود.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("badking.hybrid.jwt")

# تنها الگوریتمهایی که مجازاند. پیشفرض HS256 — متقارن، ساده و برای
# توکنهای صادرشده توسط自身 مناسب. ASYMMETRIC هم پشتیبانی میشود ولی فقط
# وقتی صریحاً در لیست مجاز قرار گیرد.
DEFAULT_ALGORITHMS = ("HS256",)


class JWTError(Exception):
    """پایه خطاهای JWT — پیامها هرگز شامل توکن نمیشوند."""


class JWTNotConfigured(JWTError):
    """کلیدی برای verification تنظیم نشده است (وضعیت NOT_VERIFIED)."""


class JWTVerificationFailed(JWTError):
    """توکن نامعتبر است (امضا، claim، ساختار، ...)."""


@dataclass(frozen=True)
class JWTVerifier:
    """اعتبارسنج JWT با الگوریتمهای صریح و محدود.

    Args:
        key: کلید secret (برای HS*) یا کلید عمومی (برای RS*/ES*).
        algorithms: تاپل الگوریتمهای مجاز. پیشفرض ``("HS256",)``.
        issuer: در صورت تنظیم، بررسی میشود.
        audience: در صورت تنظیم، بررسی میشود.
        leeway: تحمل ثانهای برای exp/nbf/iat.
        require: تاپل claimهایی که باید وجود داشته باشند (مثلاً ``("exp",)``).

    نکته امنیتی:
        الگوریتم همیشه از ``algorithms`` خوانده میشود، نه از هدر توکن.
        این همان جلوگیری از Algorithm Confusion است.
    """

    key: str | bytes
    algorithms: tuple[str, ...] = DEFAULT_ALGORITHMS
    issuer: str | None = None
    audience: str | None = None
    leeway: float = 0
    require: tuple[str, ...] = ("exp",)

    def __post_init__(self) -> None:
        if not self.key:
            raise JWTNotConfigured("کلید JWT خالی است")
        if not self.algorithms:
            raise JWTNotConfigured("هیچ الگوریتم مجاز JWT تنظیم نشده است")
        # الگوریتم none هرگز نباید در لیست مجاز باشد.
        low = tuple(a.lower() for a in self.algorithms)
        if "none" in low:
            raise JWTNotConfigured("الگوریتم 'none' مجاز نیست")
        # الگوریتمهای مجاز را محدود به لیست شناختهشده PyJWT میکنیم تا
        # هیچ الگوریتم ناشناختهای وارد نشود.
        try:
            import jwt.algorithms as _alg

            # get_default_algorithms در تمام نسخههای PyJWT 2.x موجود است.
            allowed = set(_alg.get_default_algorithms().keys())
            unknown = [a for a in self.algorithms if a not in allowed]
            if unknown:
                raise JWTNotConfigured(f"الگوریتم ناشناخته: {unknown}")
        except ImportError as exc:  # pragma: no cover - وابستگی الزامی است
            raise JWTNotConfigured("PyJWT نصب نشده است") from exc

    def verify(self, token: str) -> dict[str, Any]:
        """توکن را تأیید و payload را برمیگرداند.

        در صورت هرگونه نقص، ``JWTVerificationFailed`` میدهد. پیام خطا
        حاوی توکن یا بخشهایی از آن نیست.
        """
        if not isinstance(token, str) or not token:
            raise JWTVerificationFailed("توکن JWT خالی یا نامعتبر است")
        # ساختار باید دقیقاً سه قسمت base64url باشد.
        if token.count(".") != 2:
            raise JWTVerificationFailed("ساختار توکن JWT نامعتبر است")

        try:
            import jwt  # PyJWT
        except ImportError as exc:  # pragma: no cover
            raise JWTNotConfigured("PyJWT نصب نشده است") from exc

        options: dict[str, bool] = {
            "require": list(self.require),
        }
        # الگوریتم صریح — از هدر توکن خوانده نمیشود (جلوگیری از confusion).
        try:
            payload = jwt.decode(
                token,
                self.key,
                algorithms=list(self.algorithms),
                issuer=self.issuer,
                audience=self.audience,
                leeway=self.leeway,
                options=options,
            )
        except Exception as exc:
            # پیام اصلی PyJWT ممکن است شامل توکن یا claim حساس باشد —
            # آنرا منتقل نمیکنیم. فقط نوع کلاس خطا را (بدن جزئیات) میگیریم.
            reason = type(exc).__name__
            logger.warning("JWT verification failed: %s", reason)
            raise JWTVerificationFailed(f"توکن JWT نامعتبر است ({reason})") from None

        if not isinstance(payload, dict):
            raise JWTVerificationFailed("payload توکن JWT نامعتبر است")
        return payload


def make_verifier(
    key: str | bytes | None = None,
    algorithms: tuple[str, ...] = DEFAULT_ALGORITHMS,
    issuer: str | None = None,
    audience: str | None = None,
    leeway: float = 0,
    require: tuple[str, ...] = ("exp",),
) -> JWTVerifier | None:
    """سازنده راحت: بدون کلید ``None`` برمیگرداند (وضعیت NOT_VERIFIED)."""
    if key is None:
        return None
    return JWTVerifier(
        key=key,
        algorithms=algorithms,
        issuer=issuer,
        audience=audience,
        leeway=leeway,
        require=require,
    )
