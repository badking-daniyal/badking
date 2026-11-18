"""خطاها — ok=false تبدیل به exception میشود."""

from __future__ import annotations

from typing import Any


class BaleError(Exception):
    """پایه تمام خطاهای BADKING."""

    def __init__(self, message: str, *, code: int | None = None, description: str | None = None,
                 parameters: dict[str, Any] | None = None, method: str | None = None):
        super().__init__(message)
        self.code = code
        self.description = description
        self.parameters = parameters or {}
        self.method = method

    @property
    def retry_after(self) -> float | None:
        v = self.parameters.get("retry_after")
        return float(v) if v is not None else None


class UnauthorizedError(BaleError):
    """توکن نامعتبر — error_code 401 (docs.bale.ai/#getme)."""


class RateLimitError(BaleError):
    """محدودیت نرخ — خطای 429 با retry_after."""


class BadRequestError(BaleError):
    """پارامتر نامعتبر."""


class NetworkError(BaleError):
    """قطع اتصال / timeout."""


class StopPropagation(Exception):
    """جلوگیری از اجرای هندلرهای بعدی."""


ERROR_CLASSES = {
    401: UnauthorizedError,
    400: BadRequestError,
    429: RateLimitError,
}


def raise_for_response(data: dict[str, Any], method: str | None = None) -> dict[str, Any]:
    """پاسخ API را بررسی و در صورت خطا exception پرتاب میکند."""
    if data.get("ok") is True:
        return data.get("result")
    code = data.get("error_code")
    desc = data.get("description") or "خطای نامشخص بله"
    params = data.get("parameters") or {}
    cls = ERROR_CLASSES.get(code, BaleError)
    raise cls(
        f"{desc} (code={code}, method={method})",
        code=code,
        description=desc,
        parameters=params,
        method=method,
    )
