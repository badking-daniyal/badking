"""Self Client Reliability — تفسیر خطا، Flood Wait و correlation کمکی.

این ماژول روی لایه transport مینشیند و هیچ رفتار شبکهای را تغییر نمیدهد.
فقط خطاهایی که سرور در پیام میفرستد را به استثنای قابل فهم تبدیل میکند.
"""

from __future__ import annotations

from dataclasses import dataclass

from .proto import get_int, get_str
from .transport import RpcFailed

# شماره فیلدهای خطا — همان جدول auth.py (منبع: سورس aiobale 0.3.9)
ERROR_CODE_FIELD = 15
ERROR_MESSAGE_FIELD = 16
RETRY_AFTER_FIELD = 17

# کدهای خطای شناختهشده بله (با منبع متنی — بدون حدس شماره فیلد)
FLOOD_CODES = frozenset({429})
AUTH_CODES = frozenset({400, 401, 403})
SERVER_CODES = frozenset({500, 502, 503, 504})


@dataclass
class RpcErrorInfo:
    """اطلاعات خطای استخراجشده از پاسخ سرور."""

    code: int
    message: str
    retry_after: float | None

    @property
    def is_flood(self) -> bool:
        return self.code in FLOOD_CODES or self.retry_after is not None

    @property
    def is_auth(self) -> bool:
        return self.code in AUTH_CODES

    @property
    def is_server(self) -> bool:
        return self.code in SERVER_CODES


def parse_rpc_error(frame: bytes) -> RpcErrorInfo | None:
    """اگر پاسخ حاوی خطا باشد، آنرا استخراج میکند؛ وگرنه None.

    از همان رمزگشای protobuf استفاده میکند تا شماره فیلدها حدس زده نشود.
    """
    from .proto import decode

    msg = decode(frame)
    code = get_int(msg, ERROR_CODE_FIELD)
    if not code:
        return None
    retry = get_int(msg, RETRY_AFTER_FIELD)
    return RpcErrorInfo(
        code=code,
        message=get_str(msg, ERROR_MESSAGE_FIELD) or f"خطای سرور (کد {code})",
        retry_after=float(retry) if retry else None,
    )


def raise_for_rpc_error(frame: bytes) -> None:
    """در صورت وجود خطا در پاسخ، RpcFailed پرتاب میکند."""
    info = parse_rpc_error(frame)
    if info is not None:
        raise RpcFailed(
            info.message,
            code=info.code,
            retry_after=info.retry_after,
        )
