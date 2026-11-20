"""گوش دادن به رویدادهای self-bot.

هدف: هر پیامی که در حساب شخصی میآید را بگیری و پردازش کنی.

    python 12_selfbot_events.py

⚠️ ریسک حساب. با آگاهی استفاده کن.

نکته: SelfBot فقط رویداد «پیام ورودی» را از طریق ``@bot.on(...)`` ارائه
میدهد. رویدادهای ویرایش/حذف/خواندن بهصورت هندلر اختصاصی وجود ندارند؛
برای آنها از ``@bot.on_raw`` و تفسیر frame خام استفاده کن (پیشرفته).
"""

import asyncio
from datetime import datetime

from badking import SelfBot, hybrid_warning

# کلمههایی که میخواهی بهشان واکنش بدهی
KEYWORDS = {"فوری", "اضطراری", "کمک"}


async def main() -> None:
    print(hybrid_warning())

    bot = SelfBot(session="badking.session")

    @bot.on()
    async def on_message(message):
        """هر پیام ورودی."""
        text = message.text or ""
        sender = message.sender_id

        print(f"[{datetime.now():%H:%M:%S}] {sender}: {text[:80]}")

        # واکنش به کلمه کلیدی (پاسخ مستقیم روی همان پیام)
        if any(kw in text for kw in KEYWORDS):
            await message.reply("پیامت را دیدم. تا ۱۵ دقیقه جواب میدهم.")

    await bot.connect()
    me = await bot.get_me()
    print(f"گوش میدهم روی {me.first_name or me.id}...")

    # تا وقتی Ctrl+C نزنی میماند
    try:
        await bot.run_until_disconnected()
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
