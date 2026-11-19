"""ربات خوش‌آمدگو — ساده‌ترین ربات ممکن.

هدف: در سه خط بفهمی ربات بله چطور کار می‌کند.

    pip install badking
    set BADKING_TOKEN=123456:ABC...     # ویندوز
    export BADKING_TOKEN=123456:ABC...  # لینوکس و مک
    python 01_hello.py

توکن را از @botfather در بله بگیر.
"""

import asyncio
import os

from badking import Bot, F


async def main() -> None:
    token = os.environ.get("BADKING_TOKEN")
    if not token:
        raise SystemExit("BADKING_TOKEN را تنظیم کن. توکن از @botfather می‌آید.")

    bot = Bot(token)

    @bot.on_message(F.text == "/start")
    async def start(message):
        await message.reply(
            f"سلام {message.from_user.first_name}!\n"
            "من یک ربات نمونه‌ام. هر چیزی بنویسی، همان را برمی‌گردانم."
        )

    @bot.on_message(F.text)
    async def echo(message):
        await message.reply(message.text)

    print("ربات روشن شد. در بله به آن پیام بده.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
