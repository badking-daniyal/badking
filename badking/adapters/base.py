"""رابط مشترک پلتفرم — همان کد ربات روی بله، تلگرام، ایتا، روبیکا.

قاعده: هر پلتفرم فقط پیامها را به Update استاندارد BADKING تبدیل میکند.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..types.update import Update


class PlatformAdapter(Protocol):
    name: str

    async def fetch_updates(self, offset: int | None = None) -> list[Update]: ...
    async def send_message(self, chat_id: int | str, text: str, **kwargs: Any) -> Any: ...
    async def close(self) -> None: ...


class AdapterRegistry:
    """ثبت و مدیریت adapterها."""

    def __init__(self):
        self._adapters: dict[str, Any] = {}

    def register(self, name: str, adapter: Any) -> None:
        self._adapters[name] = adapter

    def get(self, name: str) -> Any:
        if name not in self._adapters:
            raise KeyError(f"adapter '{name}' ثبت نشده است")
        return self._adapters[name]

    def names(self) -> list[str]:
        return list(self._adapters.keys())
