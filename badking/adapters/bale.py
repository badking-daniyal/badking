"""BaleAdapter — پلتفرم پیشفرض BADKING."""

from __future__ import annotations

from typing import Any

from ..core.bot import Bot
from ..types.update import Update
from .base import PlatformAdapter


class BaleAdapter:
    name = "bale"

    def __init__(self, bot: Bot):
        self.bot = bot

    async def fetch_updates(self, offset: int | None = None) -> list[Update]:
        return await self.bot.get_updates(offset=offset)

    async def send_message(self, chat_id: int | str, text: str, **kwargs: Any) -> Any:
        return await self.bot.send_message(chat_id, text, **kwargs)

    async def close(self) -> None:
        await self.bot.close()
