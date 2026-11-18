"""Router — هندلرها را بر اساس نوع آپدیت و فیلترها اجرا میکند."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from ..types.update import Update
from .errors import StopPropagation


@dataclass
class Handler:
    callback: Callable[..., Any]
    filters: list[Callable[[Any], bool]] = field(default_factory=list)
    priority: int = 0
    kind: str | None = None  # محدود به نوع آپدیت: message / callback_query / edited_message

    def check(self, obj: Any) -> bool:
        return all(f(obj) for f in self.filters)

    async def call(self, obj: Any, update: Update, bot: Any, data: dict[str, Any]) -> Any:
        sig = inspect.signature(self.callback)
        kwargs: dict[str, Any] = {}
        for name, param in sig.parameters.items():
            if name in data:
                kwargs[name] = data[name]
            elif name in ("bot", "b", "client", "bk", "badking"):
                # اسامی رایجی که کاربران برای پارامتر bot میدهند
                kwargs[name] = bot
            elif name in ("update",):
                kwargs[name] = update
            elif name in ("message", "msg"):
                # اگر شیء هندلر خودش پیام است (message handler) همان را بده،
                # وگرنه از callback_query.message بگیر
                kwargs[name] = obj if hasattr(obj, "message_id") else update.effective_message
            elif name in ("callback_query", "query", "callback"):
                kwargs[name] = update.callback_query
            elif name in ("user", "from_user"):
                m = update.effective_message
                cq = update.callback_query
                kwargs[name] = (cq.from_user if cq else (m.from_user if m else None))
            elif name in ("state", "fsm"):
                if "state" in data:
                    kwargs[name] = data["state"]
            elif param.default is not inspect.Parameter.empty:
                continue
        result = self.callback(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result


class Router:
    """مجموعه هندلرها؛ قابل ترکیب با include_router."""

    def __init__(self, name: str | None = None):
        self.name = name
        self.handlers: list[Handler] = []
        self.children: list[Router] = []

    def message(self, *filters: Callable[[Any], bool], priority: int = 0):
        def deco(fn: Callable[..., Any]):
            self.handlers.append(Handler(fn, list(filters), priority))
            return fn
        return deco

    def callback_query(self, *filters: Callable[[Any], bool], priority: int = 0):
        def deco(fn: Callable[..., Any]):
            # نیازی به only_callback نیست: propagate خودش شیء callback_query
            # را به هندلرهای ثبتشده با callback_query میدهد.
            self.handlers.append(Handler(fn, list(filters), priority, kind="callback_query"))
            return fn
        return deco

    def edited_message(self, *filters: Callable[[Any], bool], priority: int = 0):
        def deco(fn: Callable[..., Any]):
            self.handlers.append(Handler(fn, list(filters), priority, kind="edited_message"))
            return fn
        return deco

    def include_router(self, router: "Router") -> None:
        self.children.append(router)

    def _all_handlers(self) -> list[Handler]:
        result = list(self.handlers)
        for child in self.children:
            result.extend(child._all_handlers())
        return sorted(result, key=lambda h: -h.priority)

    async def propagate(self, update: Update, bot: Any, data: dict[str, Any]) -> bool:
        for handler in self._all_handlers():
            # انتخاب شیء مناسب بر اساس نوع هندلر
            if handler.kind == "callback_query":
                obj = update.callback_query
                if obj is None:
                    continue
            elif handler.kind == "edited_message":
                obj = update.edited_message
                if obj is None:
                    continue
            else:
                # هندلر پیام: فقط وقتی message واقعی وجود دارد اجرا شود
                # (نه وقتی که آپدیت callback_query است)
                if update.callback_query is not None:
                    continue
                obj = update.message or update.effective_message
                if obj is None:
                    continue

            try:
                if not handler.check(obj):
                    continue
            except Exception:
                continue
            try:
                await handler.call(obj, update, bot, data)
            except StopPropagation:
                # هندلر صریحاً خواست زنجیره متوقف شود (همان نتیجه اولین تطابق)
                return True
            return True  # اولین هندلر تطابق یافته، بقیه را متوقف میکند
        return False
