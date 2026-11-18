"""پرداخت رسمی بله — فاکتور، PreCheckout، بررسی تراکنش، درخواست بررسی.

منبع: docs.bale.ai (sendInvoice, answerPreCheckoutQuery, askReview, inquireTransaction)
"""

from __future__ import annotations

from typing import Any

from ..types.message import Message


class PaymentToolkit:
    """متدهای پرداخت را روی Bot client اضافه میکند."""

    def __init__(self, bot: Any):
        self.bot = bot

    async def send_invoice(
        self,
        chat_id: int | str,
        title: str,
        description: str,
        payload: str,
        currency: str,
        prices: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Message:
        """ارسال فاکتور. prices: [{"label": "...", "amount": 1000}, ...]"""
        return Message.model_validate(await self.bot.request("sendInvoice", {
            "chat_id": chat_id,
            "title": title,
            "description": description,
            "payload": payload,
            "currency": currency,
            "prices": prices,
            **kwargs,
        }))

    async def create_invoice_link(self, title: str, description: str, payload: str,
                                  currency: str, prices: list[dict[str, Any]],
                                  **kwargs: Any) -> str:
        """ساخت لینک فاکتور برای اشتراکگذاری."""
        return str(await self.bot.request("createInvoiceLink", {
            "title": title, "description": description, "payload": payload,
            "currency": currency, "prices": prices, **kwargs,
        }))

    async def answer_pre_checkout(self, pre_checkout_query_id: str, ok: bool = True,
                                  error_message: str | None = None) -> bool:
        """حتماً ظرف.timeout پاسخ داده شود (پیشفرض قابلتنظیم 10 ثانیه)."""
        payload: dict[str, Any] = {
            "pre_checkout_query_id": pre_checkout_query_id, "ok": ok,
        }
        if not ok and error_message:
            payload["error_message"] = error_message
        return bool(await self.bot.request("answerPreCheckoutQuery", payload))

    async def answer_shipping(self, shipping_query_id: str, ok: bool = True,
                              **kwargs: Any) -> bool:
        return bool(await self.bot.request("answerShippingQuery", {
            "shipping_query_id": shipping_query_id, "ok": ok, **kwargs,
        }))

    async def ask_review(self, chat_id: int | str, **kwargs: Any) -> Any:
        return await self.bot.request("askReview", {"chat_id": chat_id, **kwargs})

    async def inquire_transaction(self, **kwargs: Any) -> Any:
        return await self.bot.request("inquireTransaction", kwargs)
