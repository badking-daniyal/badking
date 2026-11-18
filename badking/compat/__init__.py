"""لایه سازگاری — کدهای نوشتهشده برای aiogram / python-telegram-bot راحتتر منتقل شوند.

این لایه فقط alias و الگوی آشنا فراهم میکند؛ هسته BADKING همان است.
"""

from __future__ import annotations

from ..core.bot import Bot as BadkingBot
from ..core.dispatcher import Dispatcher as BadkingDispatcher
from ..filters.magic import F as BadkingF


class Bot(BadkingBot):
    """سازگار با aiogram: Bot(token)."""

    @property
    def session(self):
        return self


class Dispatcher(BadkingDispatcher):
    """سازگار با aiogram: Dispatcher()."""


F = BadkingF


# الگوی python-telegram-bot: Application.builder().token(...).build()
class _ApplicationBuilder:
    def __init__(self):
        self._token = None

    def token(self, token: str) -> "_ApplicationBuilder":
        self._token = token
        return self

    def build(self) -> "_Application":
        return _Application(self._token)


class _Application:
    def __init__(self, token: str):
        self.bot = Bot(token)
        self.dp = Dispatcher()

    def add_handler(self, handler: Any) -> None:
        """پشتیبانی ساده از هندلرهای ثبتشده روی dp."""

    def run_polling(self) -> None:
        import asyncio
        asyncio.run(self.bot.polling(self.dp))


class Application:
    @staticmethod
    def builder() -> _ApplicationBuilder:
        return _ApplicationBuilder()
