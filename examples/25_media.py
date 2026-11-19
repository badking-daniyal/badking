"""رسانه: دانلود، آپلود، کش، اعتبارسنجی.

هدف: فایل‌ها را امن مدیریت کن.

    python 25_media.py

ربات را روشن کن، یک عکس بفرست — دانلود می‌شود، چک می‌شود، و
مسیرش را می‌گیری.
"""

import asyncio
import os

from badking import Bot, F, MediaEngine, MediaError


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    engine = MediaEngine(
        bot,
        cache_dir=".cache/media",
        max_size=20 * 1024 * 1024,  # ۲۰ مگابایت
    )

    @bot.on_message(F.photo)
    async def on_photo(message):
        # بزرگ‌ترین سایز را بردار
        photo = message.photo[-1]

        try:
            # اول اعتبارسنجی، بعد دانلود
            info = await engine.info(photo.file_id)
            engine.validate(info)

            async def progress(done: int, total: int) -> None:
                if total:
                    print(f"  {done * 100 // total}%")

            path = await engine.download(
                photo.file_id,
                file_name="photo.jpg",
                on_progress=progress,
            )

            await message.reply(
                f"دانلود شد:\n"
                f"  مسیر: {path.name}\n"
                f"  حجم: {info.human_size()}\n"
                f"  نوع: {info.mime_type or 'نامشخص'}"
            )

        except MediaError as exc:
            await message.reply(f"نشد:\n{exc}")

    @bot.on_message(F.document)
    async def on_document(message):
        doc = message.document

        try:
            info = await engine.info(doc.file_id)
            engine.validate(info)

            path = await engine.download(doc.file_id, file_name=doc.file_name)
            await message.reply(f"ذخیره شد: {path.name} ({info.human_size()})")

        except MediaError as exc:
            await message.reply(f"رد شد:\n{exc}")

    @bot.on_message(F.text == "/cache")
    async def cache_status(message):
        usage = engine.disk_usage()
        await message.reply(
            f"کش:\n"
            f"  فایل‌ها: {usage['cache_files']}\n"
            f"  حجم: {usage['cache_bytes'] // 1024} کیلوبایت\n"
            f"  فضای آزاد: {usage['disk_free'] // (1024**3)} گیگابایت"
        )

    @bot.on_message(F.text == "/clear")
    async def clear(message):
        count = engine.clear_cache()
        await message.reply(f"{count} فایل پاک شد.")

    print("موتور رسانه روشن شد.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
