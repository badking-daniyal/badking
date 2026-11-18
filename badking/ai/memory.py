"""حافظه بلندمدت ربات — قویتر از aiobale (که اصلاً لایه AI ندارد)."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class MemoryItem:
    role: str
    content: str
    timestamp: float
    meta: dict[str, Any] | None = None


class Memory:
    """حافظه مکالمه به ازای هر کاربر + حافظه حقایق (facts)."""

    def __init__(self, max_messages: int = 50):
        if max_messages <= 0:
            raise ValueError("max_messages باید مثبت باشد (0 یعنی برش خنثی میشود)")
        self.max_messages = max_messages
        self._messages: dict[str, list[MemoryItem]] = defaultdict(list)
        self._facts: dict[str, dict[str, Any]] = defaultdict(dict)

    def add(self, user_key: str, role: str, content: str, **meta: Any) -> None:
        self._messages[user_key].append(MemoryItem(role, content, time.time(), meta or None))
        if len(self._messages[user_key]) > self.max_messages:
            self._messages[user_key] = self._messages[user_key][-self.max_messages:]

    def history(self, user_key: str, limit: int | None = None) -> list[dict[str, str]]:
        msgs = self._messages.get(user_key, [])
        if limit:
            msgs = msgs[-limit:]
        return [{"role": m.role, "content": m.content} for m in msgs]

    def set_fact(self, user_key: str, name: str, value: Any) -> None:
        self._facts[user_key][name] = value

    def get_fact(self, user_key: str, name: str, default: Any = None) -> Any:
        return self._facts[user_key].get(name, default)

    def facts(self, user_key: str) -> dict[str, Any]:
        return dict(self._facts.get(user_key, {}))

    def clear(self, user_key: str) -> None:
        self._messages.pop(user_key, None)
        self._facts.pop(user_key, None)
