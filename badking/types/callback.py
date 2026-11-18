"""CallbackQuery و PreCheckoutQuery — منبع: docs.bale.ai"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import BaleModel
from .message import Message
from .user import User


class CallbackQuery(BaleModel):
    id: str
    from_user: User = Field(alias="from")
    data: str | None = None
    message: Message | None = None
    chat_instance: str | None = None
    inline_message_id: str | None = None

    @property
    def callback_data(self) -> str | None:
        """سازگار با F.callback_data و الگوی aiogram (بله فیلد را data میفرستد)."""
        return self.data

    async def answer(self, text: str | None = None, **kwargs: Any) -> bool:
        """حتماً فراخوانی شود وگرنه دکمه در حالت انتظار میماند (docs.bale.ai)."""
        from ._context import current_bot

        bot = current_bot.get()
        if bot is None:
            raise RuntimeError("answer() فقط داخل Dispatcher کار میکند")
        return await bot.answer_callback_query(self.id, text=text, **kwargs)


class PreCheckoutQuery(BaleModel):
    id: str
    from_user: User = Field(alias="from")
    currency: str
    total_amount: int
    invoice_payload: str
    shipping_option_id: str | None = None
    order_info: Any | None = None
