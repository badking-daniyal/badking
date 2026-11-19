"""مدیریت گروه: ادمین، سکوت، اخراج.

هدف: رباتی که در گروه نظم برقرار می‌کند.

    python 05_group_admin.py

ربات را در گروه ادمین کن، وگرنه NotAdminError می‌گیری.
"""

import asyncio
import os
from datetime import datetime, timedelta

from badking import Bot, F, NotAdminError


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    def is_admin(message) -> bool:
        """آیا فرستنده ادمین است؟"""
        return message.from_user.id in ADMIN_IDS

    ADMIN_IDS = {123456789}  # شناسه خودت را بگذار

    @bot.on_message(F.text == "/ban", F.chat.type.in_({"group", "supergroup"}))
    async def ban(message):
        if not is_admin(message):
            await message.reply("این دستور برای ادمین‌هاست.")
            return

        # پیام باید ریپلای باشد
        if not message.reply_to_message:
            await message.reply("روی پیام کسی ریپلای کن و /ban بزن.")
            return

        target = message.reply_to_message.from_user
        try:
            await bot.ban_chat_member(message.chat.id, target.id)
            await message.reply(f"{target.first_name} اخراج شد.")
        except NotAdminError:
            await message.reply("من ادمین نیستم. اول ادمینم کن.")

    @bot.on_message(F.text.startswith("/mute"))
    async def mute(message):
        if not is_admin(message) or not message.reply_to_message:
            return

        # /mute 10  → ده دقیقه
        parts = message.text.split()
        minutes = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
        until = datetime.now() + timedelta(minutes=minutes)

        target = message.reply_to_message.from_user
        await bot.restrict_chat_member(
            message.chat.id,
            target.id,
            until_date=until,
            can_send_messages=False,
        )
        await message.reply(f"{target.first_name} تا {minutes} دقیقه ساکت شد.")

    @bot.on_message(F.text == "/unban")
    async def unban(message):
        if not is_admin(message) or not message.reply_to_message:
            return
        target = message.reply_to_message.from_user
        await bot.unban_chat_member(message.chat.id, target.id)
        await message.reply(f"{target.first_name} آزاد شد.")

    @bot.on_message(F.text == "/info")
    async def group_info(message):
        chat = await bot.get_chat(message.chat.id)
        count = await bot.get_chat_member_count(message.chat.id)
        await message.reply(
            f"نام: {chat.title}\n"
            f"شناسه: {chat.id}\n"
            f"اعضا: {count}\n"
            f"نوع: {chat.type}"
        )

    @bot.on_message(F.new_chat_members)
    async def welcome(message):
        for member in message.new_chat_members:
            await message.reply(
                f"خوش آمدی {member.first_name}! 👋"
            )

    print("ربات روشن شد. در گروه ادمینش کن.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
