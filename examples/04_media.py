"""ارسال رسانه: عکس، فایل، و آلبوم.

هدف: فایل بفرستی، کپشن بگذاری، و آلبوم بسازی.

    python 04_media.py
"""

import asyncio
import os
from pathlib import Path

from badking import Bot, F, MediaError


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    @bot.on_message(F.text == "/photo")
    async def send_photo(message):
        # از مسیر فایل
        await message.reply_photo(
            "photo.jpg",
            caption="این یک عکس است",
        )

    @bot.on_message(F.text == "/file")
    async def send_file(message):
        path = Path("report.pdf")
        if not path.exists():
            await message.reply("فایل report.pdf پیدا نشد.")
            return

        try:
            await message.reply_document(
                str(path),
                caption=f"گزارش — {path.stat().st_size / 1024:.0f} کیلوبایت",
            )
        except MediaError as exc:
            # خطای رسانه همیشه راه‌حل دارد
            await message.reply(f"ارسال نشد: {exc.hint}")

    @bot.on_message(F.text == "/album")
    async def send_album(message):
        # آلبوم: چند عکس در یک پیام
        await bot.send_media_group(
            message.chat.id,
            media=[
                {"type": "photo", "media": "1.jpg", "caption": "اول"},
                {"type": "photo", "media": "2.jpg"},
                {"type": "photo", "media": "3.jpg"},
            ],
        )

    @bot.on_message(F.photo)
    async def got_photo(message):
        # بزرگ‌ترین سایز عکس را بگیر
        photo = message.photo[-1]
        await message.reply(
            f"عکس گرفتم: {photo.width}×{photo.height}\n"
            f"حجم: {photo.file_size:,} بایت"
        )

    @bot.on_message(F.document)
    async def got_document(message):
        doc = message.document
        await message.reply(
            f"فایل گرفتم: {doc.file_name}\n"
            f"نوع: {doc.mime_type}\n"
            f"حجم: {doc.file_size:,} بایت"
        )

    print("ربات روشن شد. /photo یا /file یا /album را بزن.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
