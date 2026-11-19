"""مانیتور کانال: عضو جدید، خروج، آمار.

هدف: بدانی چه کسی آمد، چه کسی رفت، و کانال چطور رشد می‌کند.

    python 19_channel_monitor.py

ربات را در کانال ادمین کن تا رویدادها را بگیری.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from badking import Bot, F

LOG_FILE = Path("channel_events.jsonl")
ADMIN_ID = 123456789


def log_event(event_type: str, data: dict) -> None:
    """رویداد را به فایل اضافه می‌کند (JSON Lines)."""
    record = {
        "type": event_type,
        "at": datetime.now().isoformat(),
        **data,
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_events(limit: int = 100) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line) for line in lines[-limit:] if line]


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    @bot.on_message(F.new_chat_members)
    async def member_joined(message):
        for member in message.new_chat_members:
            log_event(
                "join",
                {
                    "user_id": member.id,
                    "name": member.first_name,
                    "username": member.username,
                    "chat_id": message.chat.id,
                },
            )
            print(f"+ {member.first_name} ({member.id})")

    @bot.on_message(F.left_chat_member)
    async def member_left(message):
        member = message.left_chat_member
        log_event(
            "leave",
            {
                "user_id": member.id,
                "name": member.first_name,
                "chat_id": message.chat.id,
            },
        )
        print(f"- {member.first_name} ({member.id})")

    @bot.on_message(F.text == "/stats")
    async def stats(message):
        if message.from_user.id != ADMIN_ID:
            return

        events = read_events(1000)
        joins = sum(1 for e in events if e["type"] == "join")
        leaves = sum(1 for e in events if e["type"] == "leave")

        count = await bot.get_chat_member_count(message.chat.id)

        await message.reply(
            f"آمار کانال:\n"
            f"  اعضای فعلی: {count}\n"
            f"  ورود (آخرین ۱۰۰۰ رویداد): {joins}\n"
            f"  خروج: {leaves}\n"
            f"  خالص: {joins - leaves:+d}"
        )

    @bot.on_message(F.text == "/recent")
    async def recent(message):
        if message.from_user.id != ADMIN_ID:
            return

        events = read_events(10)
        if not events:
            await message.reply("رویدادی ثبت نشده.")
            return

        lines = []
        for event in reversed(events):
            mark = "+" if event["type"] == "join" else "-"
            time = event["at"][11:16]
            lines.append(f"{mark} {time} {event.get('name', '?')}")

        await message.reply("آخرین رویدادها:\n" + "\n".join(lines))

    print("مانیتور کانال روشن شد.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
