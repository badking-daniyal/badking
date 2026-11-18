"""Business API — مسیر جداگانه با سهمیه نرخ مستقل.

منبع: docs.bale.ai — فقط چت شخصی، ارسال فایل فقط با file_id.
متدها: getMe, sendMessage, forwardMessage, sendPhoto, sendVideo, sendAudio, sendDocument.
"""

from __future__ import annotations

from typing import Any

from ..core.bot import Bot
from ..types.message import Message


class BusinessBot(Bot):
    """همان Bot ولی با business=True → base_url شامل /business میشود."""

    def __init__(self, token: str, **kwargs: Any):
        kwargs["business"] = True
        super().__init__(token, **kwargs)

    async def send_file_by_id(self, chat_id: int | str, kind: str, file_id: str,
                              **kwargs: Any) -> Message:
        """ارسال فایل فقط با file_id (قاعده Business API)."""
        method = {
            "photo": "sendPhoto", "video": "sendVideo",
            "audio": "sendAudio", "document": "sendDocument",
        }.get(kind)
        if not method:
            raise ValueError(f"نوع فایل نامعتبر: {kind}")
        return Message.model_validate(await self.request(method, {
            "chat_id": chat_id, kind: file_id, **kwargs,
        }))
