"""Message و MessageEntity — منبع: docs.bale.ai/#message , #messageentity"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .chat import Chat
from .common import BaleModel
from .keyboard import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from .media import Animation, Audio, Contact, Document, Location, PhotoSize, Video, Voice
from .user import User


class MessageEntity(BaleModel):
    type: str
    offset: int
    length: int
    url: str | None = None
    user: User | None = None
    language: str | None = None
    custom_emoji_id: str | None = None


class MessageId(BaleModel):
    message_id: int


class Message(BaleModel):
    message_id: int
    date: int
    chat: Chat
    from_user: User | None = Field(default=None, alias="from")
    text: str | None = None
    caption: str | None = None
    entities: list[MessageEntity] | None = None
    caption_entities: list[MessageEntity] | None = None
    photo: list[PhotoSize] | None = None
    animation: Animation | None = None
    audio: Audio | None = None
    document: Document | None = None
    video: Video | None = None
    voice: Voice | None = None
    contact: Contact | None = None
    location: Location | None = None
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | dict | None = None
    reply_to_message: Any | None = None
    forward_from: User | None = None
    forward_from_chat: Chat | None = None
    forward_date: int | None = None
    new_chat_members: list[User] | None = None
    left_chat_member: User | None = None
    successful_payment: Any | None = None
    web_app_data: Any | None = None
    forum_topic_created: Any | None = None
    message_thread_id: int | None = None

    @property
    def content(self) -> str | None:
        return self.text or self.caption

    @property
    def is_command(self) -> bool:
        if not self.text:
            return False
        # فرمان ممکن است اولین entity نباشد؛ هر entity از نوع bot_command
        # که در ابتدای پیام (offset=0) باشد، فرمان محسوب میشود.
        return any(
            getattr(e, "type", None) == "bot_command" and getattr(e, "offset", None) == 0
            for e in (self.entities or [])
        )

    async def answer(self, text: str, **kwargs: Any) -> "Message":
        """پاسخ سریع به پیام (via Bot ذخیرهشده در context)."""
        from ._context import current_bot

        bot = current_bot.get()
        if bot is None:
            raise RuntimeError("answer() فقط داخل Dispatcher کار میکند")
        return await bot.send_message(self.chat.id, text, reply_to_message_id=self.message_id, **kwargs)

    async def reply(self, text: str, **kwargs: Any) -> "Message":
        """نام مستعار `answer` — پاسخ به همین پیام.

        هر دو یکیاند. `reply` نام آشناتری است و در نمونهها استفاده شده.
        """
        return await self.answer(text, **kwargs)

    async def delete(self) -> bool:
        """حذف همین پیام (via Bot ذخیرهشده در context)."""
        from ._context import current_bot

        bot = current_bot.get()
        if bot is None:
            raise RuntimeError("delete() فقط داخل Dispatcher کار میکند")
        return await bot.delete_message(self.chat.id, self.message_id)
