"""Middlewareهای آماده — زنجیره middleware زنجیرهای Dispatcher.

الگوی middleware:
    async def mw(update, data, next_call):
        ... قبل ...
        result = await next_call(update, data)
        ... بعد ...
        return result
"""

from __future__ import annotations

import time
from typing import Any, Callable

from ..observability import metrics


def logging_mw(logger: Any = None) -> Callable[..., Any]:
    """لاگ ساختاریافته هر آپدیت."""
    async def middleware(update, data, next_call):
        log = logger or __import__("logging").getLogger("badking")
        start = time.time()
        log.info("update kind=%s id=%s", update.kind, update.update_id)
        try:
            return await next_call(update, data)
        finally:
            metrics.observe("update_latency", time.time() - start)
    return middleware


def metrics_mw() -> Callable[..., Any]:
    """شمارش آپدیتها بر اساس نوع."""
    async def middleware(update, data, next_call):
        metrics.inc("updates_total", 1, kind=update.kind)
        return await next_call(update, data)
    return middleware


def antispam_mw(antispam: Any) -> Callable[..., Any]:
    """جلوگیری از اسپم قبل از رسیدن به هندلرها."""
    async def middleware(update, data, next_call):
        obj = update.effective_message or update.callback_query
        user = getattr(obj, "from_user", None) if obj else None
        if user and not antispam.is_allowed(user.id):
            metrics.inc("spam_blocked")
            return False
        return await next_call(update, data)
    return middleware
