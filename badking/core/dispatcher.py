"""Dispatcher — پردازش آپدیتها با middleware زنجیرهای و ContextVar."""

from __future__ import annotations

from typing import Any, Callable

from ..types._context import current_bot, current_update
from ..types.update import Update
from .router import Router


class Dispatcher(Router):
    """Router اصلی + middleware زنجیرهای."""

    def __init__(self, name: str | None = None, storage: Any = None, fsm_timeout: float | None = None):
        super().__init__(name)
        # همیشه یک storage پیشفرض داریم تا هندلرهایی که پارامتر state میگیرند
        # حتی بدون تنظیم صریح storage هم کار کنند (جلوگیری از TypeError).
        if storage is None:
            from ..storage.memory import MemoryStorage
            storage = MemoryStorage()
        self.middleware: list[Callable[..., Any]] = []
        self.storage = storage
        self.fsm_timeout = fsm_timeout

    def register_middleware(self, factory: Callable[..., Any]) -> None:
        self.middleware.append(factory)

    def _fsm_key(self, update: Update) -> str | None:
        """کلید پایدار چت:کاربر. در callback_query کاربر داخل query و چت داخل message است."""
        cq = update.callback_query
        msg = update.effective_message

        # کاربر: در callback_query داخل query است، وگرنه داخل پیام
        user = getattr(cq, "from_user", None) if cq is not None else None
        if user is None:
            user = getattr(msg, "from_user", None)

        # چت: از پیام (هم معمولی و هم callback_query.message)
        chat = getattr(msg, "chat", None)
        if chat is None and cq is not None:
            chat = getattr(getattr(cq, "message", None), "chat", None)

        uid = getattr(user, "id", None)
        cid = getattr(chat, "id", None)
        # callback بدون message (inline-mode): از chat_instance بهعنوان جایگزین چت استفاده کن
        if cid is None and cq is not None:
            cid = getattr(cq, "chat_instance", None) or getattr(cq, "inline_message_id", None)
        if uid is not None and cid is not None:
            return f"{cid}:{uid}"
        return str(uid or cid) if (uid or cid) is not None else None

    async def process(self, update: Update, bot: Any, data: dict[str, Any] | None = None) -> bool:
        data = dict(data or {})
        if self.storage is not None:
            from ..fsm.fsm import FSMContext
            key = self._fsm_key(update)
            if key:
                data.setdefault("state", FSMContext(self.storage, key))
        token_bot = current_bot.set(bot)
        token_update = current_update.set(update)
        try:
            async def call_next(u: Update, d: dict[str, Any]) -> bool:
                return await super(Dispatcher, self).propagate(u, bot, d)

            chain = call_next
            for mw in reversed(self.middleware):
                prev = chain

                async def wrapped(u: Update, d: dict[str, Any], _mw=mw, _prev=prev) -> bool:
                    result = _mw(u, d, _prev)
                    if hasattr(result, "__await__"):
                        result = await result
                    return result if result is not None else await _prev(u, d)

                chain = wrapped

            return await chain(update, data)
        finally:
            current_bot.reset(token_bot)
            current_update.reset(token_update)
