"""مدیریت گروه: اخطار، سکوت، اخراج، فیلتر.

هدف: یک موتور مدیریت کامل، با تاریخچه.

    python 23_moderation.py

ربات را ادمین گروه کن.
"""

import asyncio
import os

from badking import (
    Action,
    Bot,
    F,
    Moderator,
    Rule,
    SQLiteStorage,
    flood_rule,
    link_rule,
    mention_spam_rule,
)

ADMIN_ID = 123456789


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    # تخلف‌ها در SQLite می‌مانند — بعد از ری‌استارت هم هست
    mod = Moderator(
        bot,
        storage=SQLiteStorage("moderation.db"),
        warn_limit=3,
        mute_seconds=3600,
    )

    # لینک: اخطار
    mod.add_rule(link_rule(Action.WARN))

    # متن خیلی بلند: اخطار
    mod.add_rule(flood_rule(max_length=2000, action=Action.WARN))

    # منشن انبوه: سکوت یک‌ساعته
    mod.add_rule(mention_spam_rule(max_mentions=5, action=Action.MUTE))

    # کلمات ممنوع: حذف پیام
    mod.add_rule(
        Rule(
            name="banned_words",
            words=["تبلیغ", "کسب درآمد"],
            action=Action.DELETE,
        )
    )

    # هر پیام را بررسی کن
    @bot.on_message(F.text | F.caption)
    async def check(message):
        found = await mod.inspect(message)
        if found:
            print(f"تخلف: {found[0].rule} → {found[0].action.value}")

    # ---------- دستورهای ادمین ----------

    @bot.on_message(F.text == "/stats")
    async def stats(message):
        if message.from_user.id != ADMIN_ID:
            return

        s = mod.stats()
        await message.reply(
            f"مدیریت:\n"
            f"  قواعد فعال: {s['rules']}\n"
            f"  تخلف‌ها: {s['violations']}\n"
            f"  کاربران اخطارگرفته: {s['warned_users']}\n"
            f"  لیست سیاه: {s['blacklisted']}"
        )

    @bot.on_message(F.text == "/forgive")
    async def forgive(message):
        """پاسخ به پیام کسی که می‌خواهی اخطارهایش صفر شود."""
        if message.from_user.id != ADMIN_ID:
            return

        if not message.reply_to_message:
            await message.reply("روی پیام کاربر پاسخ بده.")
            return

        target = message.reply_to_message.from_user.id
        mod.reset_warns(message.chat.id, target)
        await message.reply(f"اخطارهای {target} صفر شد.")

    @bot.on_message(F.text.startswith("/ban"))
    async def ban(message):
        if message.from_user.id != ADMIN_ID:
            return

        if not message.reply_to_message:
            await message.reply("روی پیام کاربر پاسخ بده.")
            return

        target = message.reply_to_message.from_user.id
        mod.blacklist(target)
        await bot.ban_chat_member(message.chat.id, target)
        await message.reply(f"{target} اخراج شد.")

    @bot.on_message(F.text == "/rules")
    async def rules(message):
        names = "\n".join(f"  • {n}" for n in mod.rule_names())
        await message.reply(f"قواعد فعال:\n{names}")

    print("موتور مدیریت روشن شد.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
