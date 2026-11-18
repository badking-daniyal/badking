"""Conversation — ویزارد پرسش‌وپاسخ چندمرحله‌ای (مثل aiobale، ولی ساده‌تر).

مثال:
    async with Conversation(bot, chat_id) as conv:
        await conv.send("اسمت چیه؟")
        name = await conv.get_response(timeout=60)
        await conv.send(f"خوش آمدی {name.text}")

نحوه کار: یک ConversationManager به‌عنوان middleware ثبت می‌شود. وقتی برای یک چت
مکالمه‌ای فعال باشد، آپدیت‌های آن چت به صف مکالمه می‌روند و به هندلرهای عادی
نمی‌رسند. بعد از خروج از `async with`، کنترل به هندلرهای عادی برمی‌گردد.
"""

from __future__ import annotations

import asyncio
from typing import Any


class ConversationTimeout(Exception):
    """کاربر در بازه مجاز پاسخ نداد."""


class Conversation:
    """مکالمه خطی با یک چت."""

    def __init__(self, bot: Any, chat_id: int | str, manager: "ConversationManager",
                 timeout: float | None = None):
        self.bot = bot
        self.chat_id = chat_id
        self._manager = manager
        self._queue: asyncio.Queue = asyncio.Queue()
        self._default_timeout = timeout

    async def __aenter__(self) -> "Conversation":
        self._manager._register(self.chat_id, self._queue)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._manager._unregister(self.chat_id)

    async def send(self, text: str, **kwargs: Any) -> Any:
        """ارسال پیام در جریان مکالمه."""
        return await self.bot.send_message(self.chat_id, text, **kwargs)

    async def get_response(self, timeout: float | None = None) -> Any:
        """منتظر پیام بعدی کاربر می‌ماند. در صورت انقضا ConversationTimeout."""
        wait = timeout if timeout is not None else self._default_timeout
        try:
            if wait is None:
                return await self._queue.get()
            return await asyncio.wait_for(self._queue.get(), timeout=wait)
        except asyncio.TimeoutError:
            raise ConversationTimeout(
                f"کاربر در {wait} ثانیه پاسخ نداد (chat_id={self.chat_id})"
            )

    async def ask(self, text: str, timeout: float | None = None, **kwargs: Any) -> Any:
        """میان‌بر: سوال بپرس و پاسخ بگیر."""
        await self.send(text, **kwargs)
        return await self.get_response(timeout=timeout)


class ConversationManager:
    """مدیر مکالمه‌های فعال — به‌عنوان middleware در Dispatcher ثبت می‌شود."""

    def __init__(self):
        self._active: dict[str, asyncio.Queue] = {}

    @staticmethod
    def _key(chat_id: Any) -> str:
        return str(chat_id)

    def _register(self, chat_id: Any, queue: asyncio.Queue) -> None:
        self._active[self._key(chat_id)] = queue

    def _unregister(self, chat_id: Any) -> None:
        self._active.pop(self._key(chat_id), None)

    def is_active(self, chat_id: Any) -> bool:
        return self._key(chat_id) in self._active

    def conversation(self, bot: Any, chat_id: int | str, timeout: float | None = None) -> Conversation:
        """ساخت مکالمه جدید (به‌صورت async with استفاده شود)."""
        return Conversation(bot, chat_id, self, timeout=timeout)

    async def __call__(self, update: Any, data: dict[str, Any], call_next: Any) -> bool:
        """middleware: اگر چت مکالمه فعال دارد، آپدیت را به صف بده و متوقف کن."""
        msg = getattr(update, "effective_message", None) or getattr(update, "message", None)
        chat = getattr(msg, "chat", None)
        chat_id = getattr(chat, "id", None)
        if chat_id is not None:
            queue = self._active.get(self._key(chat_id))
            if queue is not None:
                await queue.put(msg)
                return True  # هندلرهای عادی اجرا نشوند
        return await call_next(update, data)
