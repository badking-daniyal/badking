"""میان‌افزار: لاگ، سنجش زمان، و کنترل دسترسی.

هدف: هر پیام از چند لایه رد شود قبل از رسیدن به هندلر.

    python 17_middleware.py
"""

import asyncio
import logging
import os
import time

from badking import Bot, F

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)
log = logging.getLogger("mw")

ADMIN_ID = 123456789
BANNED_USERS: set[int] = set()


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    # ---------- ۱. لاگ ----------
    @bot.middleware(priority=10)
    async def log_middleware(handler, event, data):
        user = getattr(event, "from_user", None)
        name = user.first_name if user else "?"
        log.info("→ %s: %s", name, (getattr(event, "text", "") or "")[:50])

        started = time.perf_counter()
        try:
            return await handler(event, data)
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            log.info("← %.0f میلی‌ثانیه", elapsed)

    # ---------- ۲. بلاک ----------
    @bot.middleware(priority=20)
    async def ban_middleware(handler, event, data):
        user = getattr(event, "from_user", None)
        if user and user.id in BANNED_USERS:
            log.info("بلاک شده: %s", user.id)
            return  # هندلر اجرا نمی‌شود
        return await handler(event, data)

    # ---------- ۳. فقط ادمین ----------
    @bot.middleware(priority=30)
    async def admin_middleware(handler, event, data):
        text = getattr(event, "text", "") or ""
        if text.startswith("/admin") and getattr(event.from_user, "id", 0) != ADMIN_ID:
            await event.reply("این دستور برای ادمین است.")
            return
        return await handler(event, data)

    # ---------- هندلرها ----------
    @bot.on_message(F.text == "/start")
    async def start(message):
        await message.reply("سلام!")

    @bot.on_message(F.text == "/admin")
    async def admin(message):
        await message.reply(f"پنل ادمین\nکاربران بلاک‌شده: {len(BANNED_USERS)}")

    @bot.on_message(F.text.startswith("/ban"))
    async def ban(message):
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            await message.reply("/ban 123456789")
            return
        BANNED_USERS.add(int(parts[1]))
        await message.reply(f"{parts[1]} بلاک شد.")

    @bot.on_message(F.text)
    async def echo(message):
        await message.reply(message.text)

    print("ربات روشن شد. /admin را با و بدون ادمین بودن امتحان کن.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
