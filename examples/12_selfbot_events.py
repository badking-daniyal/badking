"""گوش دادن به رویدادهای self-bot.

هدف: هر پیامی که در حساب شخصی می‌آید را بگیری و پردازش کنی.

    python 12_selfbot_events.py

⚠️ ریسک حساب. با آگاهی استفاده کن.
"""

import asyncio
from datetime import datetime

from badking import SelfBot, hybrid_warning

# کلمه‌هایی که می‌خواهی بهشان واکنش بدهی
KEYWORDS = {"فوری", "اضطراری", "کمک"}


async def main() -> None:
    print(hybrid_warning())

    bot = SelfBot(session="badking.session", ack_risk=True)

    @bot.on_self_message()
    async def on_message(message):
        """هر پیام ورودی."""
        text = message.text or ""
        sender = message.sender_id

        print(f"[{datetime.now():%H:%M:%S}] {sender}: {text[:80]}")

        # واکنش به کلمه کلیدی
        if any(kw in text for kw in KEYWORDS):
            await bot.send_message(
                message.chat_id,
                "پیامت را دیدم. تا ۱۵ دقیقه جواب می‌دهم.",
                reply_to=message.id,
            )

    @bot.on_self_edit()
    async def on_edit(message):
        """پیامی ویرایش شد."""
        print(f"ویرایش شد: {message.id}")

    @bot.on_self_delete()
    async def on_delete(event):
        """پیامی حذف شد."""
        print(f"حذف شد: {event.message_id} در چت {event.chat_id}")

    @bot.on_self_read()
    async def on_read(event):
        """پیام‌ها خوانده شدند."""
        print(f"خوانده شد تا پیام {event.max_id}")

    await bot.connect()
    me = await bot.get_me()
    print(f"گوش می‌دهم روی {me.first_name}...")

    # تا وقتی Ctrl+C نزنی می‌ماند
    try:
        await bot.idle()
    finally:
        await bot.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
