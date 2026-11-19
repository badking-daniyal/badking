"""فروشگاه با سبد خرید و پرداخت.

هدف: محصول ببینی، به سبد اضافه کنی، سفارش بدهی.

    python 08_shop.py

این نمونه سبد خرید را در حافظه نگه می‌دارد. برای تولید، به ۰۷ نگاه کن
که SQLite استفاده می‌کند.
"""

import asyncio
import os
from dataclasses import dataclass, field

from badking import Bot, CallbackData, F, InlineKeyboardBuilder

CartCB = CallbackData("cart", "action", "product_id")


@dataclass
class Product:
    id: int
    name: str
    price: int
    stock: int


PRODUCTS = [
    Product(1, "چای سیاه ممتاز", 85_000, 50),
    Product(2, "قهوه ترک", 120_000, 30),
    Product(3, "زعفران یک مثقال", 450_000, 10),
]

CARTS: dict[int, dict[int, int]] = {}  # user_id → {product_id: quantity}


def cart_total(user_id: int) -> int:
    cart = CARTS.get(user_id, {})
    return sum(
        next(p.price for p in PRODUCTS if p.id == pid) * qty
        for pid, qty in cart.items()
    )


def cart_text(user_id: int) -> str:
    cart = CARTS.get(user_id, {})
    if not cart:
        return "سبد خرید خالی است."

    lines = []
    for pid, qty in cart.items():
        product = next(p for p in PRODUCTS if p.id == pid)
        lines.append(f"• {product.name} × {qty} = {product.price * qty:,} تومان")

    lines.append(f"\nجمع: {cart_total(user_id):,} تومان")
    return "\n".join(lines)


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    @bot.on_message(F.text == "/shop")
    async def shop(message):
        kb = InlineKeyboardBuilder()
        for product in PRODUCTS:
            kb.button(
                f"{product.name} — {product.price:,}",
                callback_data=CartCB(action="add", product_id=product.id).pack(),
            )
        kb.button("🛒 سبد خرید", callback_data=CartCB(action="view", product_id=0).pack())
        kb.adjust(1)

        await message.reply("محصول را انتخاب کن:", reply_markup=kb.as_markup())

    @bot.on_callback(F.data.startswith("cart:add:"))
    async def add_to_cart(callback):
        data = CartCB.unpack(callback.data)
        product = next(p for p in PRODUCTS if p.id == data.product_id)

        cart = CARTS.setdefault(callback.from_user.id, {})
        current = cart.get(product.id, 0)

        if current >= product.stock:
            await callback.answer("موجودی کافی نیست", show_alert=True)
            return

        cart[product.id] = current + 1
        await callback.answer(f"{product.name} اضافه شد")

    @bot.on_callback(F.data.startswith("cart:view:"))
    async def view_cart(callback):
        user_id = callback.from_user.id
        kb = InlineKeyboardBuilder()

        if CARTS.get(user_id):
            kb.button(
                "✅ ثبت سفارش",
                callback_data=CartCB(action="checkout", product_id=0).pack(),
            )
            kb.button(
                "🗑 خالی کردن",
                callback_data=CartCB(action="clear", product_id=0).pack(),
            )
            kb.adjust(1)

        await callback.message.edit_text(
            cart_text(user_id),
            reply_markup=kb.as_markup() if CARTS.get(user_id) else None,
        )
        await callback.answer()

    @bot.on_callback(F.data.startswith("cart:checkout:"))
    async def checkout(callback):
        user_id = callback.from_user.id
        cart = CARTS.get(user_id, {})

        if not cart:
            await callback.answer("سبد خالی است", show_alert=True)
            return

        total = cart_total(user_id)

        # اینجا درگاه پرداخت را صدا بزن. PaymentToolkit را ببین.
        order_lines = [
            f"• {next(p.name for p in PRODUCTS if p.id == pid)} × {qty}"
            for pid, qty in cart.items()
        ]

        CARTS[user_id] = {}

        await callback.message.edit_text(
            "سفارش ثبت شد:\n"
            + "\n".join(order_lines)
            + f"\n\nمبلغ: {total:,} تومان\n"
            "برای پرداخت با پشتیبانی تماس بگیر."
        )
        await callback.answer("ثبت شد")

    @bot.on_callback(F.data.startswith("cart:clear:"))
    async def clear(callback):
        CARTS[callback.from_user.id] = {}
        await callback.message.edit_text("سبد خالی شد.")
        await callback.answer()

    print("فروشگاه روشن شد. /shop را بزن.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
