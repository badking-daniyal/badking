"""Self-bot: ربات روی حساب شخصی.

هدف: کاری که ربات رسمی نمی‌تواند بکند — خواندن تاریخچه، ارسال به هر چت،
دیدن مخاطبین.

    python 11_selfbot.py

⚠️ ریسک: این روش حساب را در معرض مسدود شدن می‌گذارد. با آگاهی استفاده کن.

قدم اول، یک بار:
    badking login --phone 0912...
"""

import asyncio
import os

from badking import SelfBot, hybrid_warning


async def main() -> None:
    print(hybrid_warning())

    bot = SelfBot(session="badking.session")

    await bot.connect()
    me = await bot.get_me()
    print(f"وصل شد: {me.first_name} (@{me.username})")

    # ---------- خواندن تاریخچه ----------
    # ربات رسمی نمی‌تواند پیام‌های قبل از عضویت را بخواند. self-bot می‌تواند.
    print("\nآخرین پیام‌های یک چت:")
    async for message in bot.iter_messages("me", limit=5):
        sender = message.sender_id
        text = (message.text or "")[:60]
        print(f"  [{sender}] {text}")

    # ---------- ارسال به خودت ----------
    await bot.send_message("me", "پیام آزمایشی از BADKING")
    print("\nپیام به Saved Messages فرستاده شد.")

    # ---------- مخاطبین ----------
    contacts = await bot.get_contacts()
    print(f"\n{len(contacts)} مخاطب:")
    for contact in contacts[:5]:
        print(f"  {contact.first_name} — {contact.phone}")

    # ---------- دیالوگ‌ها ----------
    dialogs = await bot.get_dialogs(limit=10)
    print(f"\n{len(dialogs)} گفتگوی اخیر:")
    for dialog in dialogs[:5]:
        print(f"  {dialog.title} ({dialog.peer_type})")

    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
