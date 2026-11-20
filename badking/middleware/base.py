"""BaseMiddleware — کلاس پایه برای میانافزارهای مبتنیبر کلاس.

Middlewareهای BADKING بهصورت تابعاند (`logging_mw`، `metrics_mw`) ولی
بسیاری از کاربران از aiobale میآیند و الگوی کلاس را میشناسند. این کلاس
یک پل ساده است: میانافزار کلاسمحور بنویس، و `as_middleware()` آن را به
تابع قابل ثبت در Dispatcher تبدیل میکند.

    class MyMiddleware(BaseMiddleware):
        async def before(self, update, bot, data):
            data["start"] = time.time()

        async def after(self, update, bot, data, result, error):
            print("پایان")

    dp.register_middleware(MyMiddleware().as_middleware())
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

MiddlewareFunc = Callable[..., Awaitable[Any]]


class BaseMiddleware:
    """پایه میانافزار کلاسمحور.

    متدها اختیاریاند. پیشفرض هیچ کاری نمیکنند تا پیادهسازی تنها بخشی
    که لازم است کافی باشد.
    """

    name: str = "base"

    async def before(self, update: Any, bot: Any, data: dict[str, Any]) -> None:
        """قبل از اجرای هندلر."""
        return None

    async def after(
        self,
        update: Any,
        bot: Any,
        data: dict[str, Any],
        result: Any = None,
        error: BaseException | None = None,
    ) -> None:
        """بعد از اجرای هندلر."""
        return None

    async def on_error(self, error: BaseException, update: Any, bot: Any) -> bool:
        """مدیریت خطا. ``True`` یعنی خطاhandled شد."""
        return False

    def as_middleware(self) -> MiddlewareFunc:
        """تبدیل به تابع قابل ثبت در Dispatcher."""

        async def middleware(update: Any, bot: Any, data: dict[str, Any] | None = None):
            ctx = data if data is not None else {}
            await self.before(update, bot, ctx)
            result = None
            error: BaseException | None = None
            try:
                result = await self._call_next(update, bot, ctx)
            except BaseException as exc:  # noqa: BLE001
                error = exc
                if not await self.on_error(exc, update, bot):
                    raise
            finally:
                await self.after(update, bot, ctx, result, error)
            return result

        return middleware

    async def _call_next(self, update: Any, bot: Any, data: dict[str, Any]) -> Any:
        """بخش اصلی میانافزار — در کلاس فرزند بازنویسی میشود."""
        return None


__all__ = ["BaseMiddleware"]
