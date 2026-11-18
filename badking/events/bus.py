"""Event Bus / PubSub — هر رویدادی را به هر جایی وصل کن."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable[..., Awaitable[Any]]]] = defaultdict(list)

    def on(self, event: str):
        def deco(fn: Callable[..., Awaitable[Any]]):
            self._handlers[event].append(fn)
            return fn
        return deco

    def subscribe(self, event: str, fn: Callable[..., Awaitable[Any]]) -> None:
        self._handlers[event].append(fn)

    async def emit(self, event: str, **payload: Any) -> None:
        # هر هندلر ایزوله است: خطای یکی بقیه را متوقف نمیکند
        for fn in list(self._handlers.get(event, [])):
            try:
                result = fn(**payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                import logging
                logging.getLogger("badking").exception("خطا در هندلر رویداد %s", event)

    def clear(self, event: str | None = None) -> None:
        if event:
            self._handlers.pop(event, None)
        else:
            self._handlers.clear()
