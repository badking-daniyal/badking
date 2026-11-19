"""روتر: پروژه بزرگ در چند فایل.

هدف: کد را بشکنی بدون اینکه هندلرها گم شوند.

    python 18_router.py

ساختار:
    main.py       ← این فایل
    shop.py       ← روتر فروشگاه
    support.py    ← روتر پشتیبانی
"""

import asyncio
import os

from badking import Bot, F, Router

# ---------- روتر فروشگاه ----------
shop_router = Router(name="shop")


@shop_router.message(F.text == "/shop")
async def shop_start(message):
    await message.reply("به فروشگاه خوش آمدی. /products را بزن.")


@shop_router.message(F.text == "/products")
async def shop_products(message):
    await message.reply("۱. چای\n۲. قهوه\n۳. زعفران")


# ---------- روتر پشتیبانی ----------
support_router = Router(name="support")


@support_router.message(F.text == "/help")
async def support_help(message):
    await message.reply("چه کمکی می‌توانم بکنم؟")


@support_router.message(F.text == "/contact")
async def support_contact(message):
    await message.reply("با پشتیبانی تماس بگیر: support@example.com")


# ---------- زیرروتر ----------
# روتر تودرتو: پشتیبانی فنی زیرمجموعه پشتیبانی
tech_router = Router(name="tech")


@tech_router.message(F.text == "/bug")
async def report_bug(message):
    await message.reply("باگ را توضیح بده. کد خطا را هم بفرست.")


support_router.include_router(tech_router)


# ---------- اصلی ----------
async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    # روترها را به ربات وصل کن
    bot.include_router(shop_router)
    bot.include_router(support_router)

    # هندلر پیش‌فرض — آخرین خط دفاع
    @bot.on_message(F.text)
    async def fallback(message):
        await message.reply(
            "متوجه نشدم. دستورها:\n"
            "/shop /products — فروشگاه\n"
            "/help /contact /bug — پشتیبانی"
        )

    print("ربات روشن شد.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
