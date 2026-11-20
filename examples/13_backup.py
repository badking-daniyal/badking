"""پشتیبان‌گیری از چت‌ها با self-bot.

هدف: تاریخچه یک چت را در JSON ذخیره کنی.

    python 13_backup.py

⚠️ ریسک حساب. با آگاهی استفاده کن.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from badking import SelfBot, hybrid_warning

CHAT = "me"          # یوزرنیم، شناسه، یا "me"
LIMIT = 1000         # چند پیام
OUTPUT = "backup.json"


async def main() -> None:
    print(hybrid_warning())

    bot = SelfBot(session="badking.session")
    await bot.connect()

    chat = await bot.get_entity(CHAT)
    print(f"پشتیبان‌گیری از: {chat.title or chat.first_name}")

    messages = []
    count = 0

    async for message in bot.iter_messages(CHAT, limit=LIMIT):
        count += 1
        messages.append(
            {
                "id": message.id,
                "date": datetime.fromtimestamp(message.date).isoformat()
                if message.date
                else None,
                "sender_id": message.sender_id,
                "text": message.text,
                "has_media": bool(message.media),
                "reply_to": message.reply_to,
            }
        )

        if count % 100 == 0:
            print(f"  {count} پیام...")

    # از قدیم به جدید
    messages.reverse()

    data = {
        "chat_id": chat.id,
        "chat_title": getattr(chat, "title", None) or getattr(chat, "first_name", None),
        "exported_at": datetime.now().isoformat(),
        "count": len(messages),
        "messages": messages,
    }

    path = Path(OUTPUT)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    size_kb = path.stat().st_size / 1024
    print(f"\n{len(messages)} پیام در {path} ذخیره شد ({size_kb:.0f} کیلوبایت)")

    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
