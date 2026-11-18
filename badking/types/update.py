"""Update — منبع: docs.bale.ai/#update

در هر آپدیت حداکثر یکی از فیلدهای اختیاری وجود دارد.
"""

from __future__ import annotations

from typing import Any

from .callback import CallbackQuery, PreCheckoutQuery
from .common import BaleModel
from .message import Message


class Update(BaleModel):
    update_id: int
    message: Message | None = None
    edited_message: Message | None = None
    callback_query: CallbackQuery | None = None
    pre_checkout_query: PreCheckoutQuery | None = None
    inline_query: Any | None = None
    shipping_query: Any | None = None
    my_chat_member: Any | None = None
    chat_member: Any | None = None

    @property
    def kind(self) -> str:
        for name in (
            "message",
            "edited_message",
            "callback_query",
            "pre_checkout_query",
            "inline_query",
            "shipping_query",
            "my_chat_member",
            "chat_member",
        ):
            if getattr(self, name) is not None:
                return name
        return "unknown"

    @property
    def effective_message(self) -> Message | None:
        return self.message or self.edited_message or (
            self.callback_query.message if self.callback_query else None
        )
