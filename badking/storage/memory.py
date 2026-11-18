"""MemoryStorage — ذخیره در حافظه (برای تست و رباتهای ساده)."""

from __future__ import annotations

import asyncio
from typing import Any

from .base import Storage


class MemoryStorage:
    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> dict[str, Any] | None:
        async with self._lock:
            v = self._data.get(key)
            return dict(v) if v is not None else None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        async with self._lock:
            self._data[key] = dict(value)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    async def keys(self) -> list[str]:
        async with self._lock:
            return list(self._data.keys())
