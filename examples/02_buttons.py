"""کیبورد شیشه‌ای و دکمه‌های تعاملی.

هدف: دکمه بسازی، کلیک را بگیری، و داده را از دکمه عبور دهی.

    python 02_buttons.py
"""

import asyncio
import os

from badking import Bot, CallbackData, F, InlineKeyboardBuilder

# داده تایپ‌دار برای دکمه. وقتی برگشت، product_id واقعاً int است.
ProductCB = CallbackData("product", "action", "product_id")

PRODUCTS = {
    1: ("چای سیاه", 85000),
    2: ("قهوه ترک", 120000),
    3: ("زعفران", 450000),
}


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    @bot.on_message(F.text == "/shop")
    async def show_shop(message):
        kb = InlineKeyboardBuilder()
        for pid, (name, price) in PRODUCTS.items():
            kb.button(
                f"{name} — {price:,} تومان",
                callback_data=ProductCB(action="view", product_id=pid).pack(),
            )
        kb.adjust(1)

        await message.reply("کدام را می‌خواهی؟", reply_markup=kb.as_markup())

    @bot.on_callback(F.data.startswith("product:"))
    async def on_product(callback):
        data = ProductCB.unpack(callback.data)
        name, price = PRODUCTS[data.product_id]

        kb = InlineKeyboardBuilder()
        kb.button(
            "خرید",
            callback_data=ProductCB(action="buy", product_id=data.product_id).pack(),
        )
        kb.button("بازگشت", callback_data="back")

        await callback.message.edit_text(
            f"{name}\nقیمت: {price:,} تومان",
            reply_markup=kb.as_markup(),
        )
        await callback.answer()

    @bot.on_callback(F.data.startswith("product:buy:"))
    async def on_buy(callback):
        data = ProductCB.unpack(callback.data)
        name, price = PRODUCTS[data.product_id]
        await callback.answer(f"سفارش {name} ثبت شد", show_alert=True)

    @bot.on_callback(F.data == "back")
    async def on_back(callback):
        await callback.answer("برگشتی")

    print("ربات روشن شد. /shop را بزن.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
