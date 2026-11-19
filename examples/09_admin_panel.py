"""پنل ادمین: آمار، کاربران، پیام همگانی.

هدف: رباتی که خودش را می‌پاید.

    python 09_admin_panel.py
"""

import asyncio
import os
import time
from collections import Counter

from badking import Bot, F, InlineKeyboardBuilder, RateLimitError, RetryPolicy

ADMIN_ID = 123456789

STATS = {
    "started": 0,
    "messages": 0,
    "commands": Counter(),
    "first_seen": time.time(),
}
USERS: set[int] = set()


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    # ارسال همگانی با تلاش مجدد — یک خطای شبکه کل کار را خراب نمی‌کند
    policy = RetryPolicy(attempts=3, base_delay=1.0)

    def is_admin(message) -> bool:
        return message.from_user.id == ADMIN_ID

    @bot.on_message(F.text == "/start")
    async def start(message):
        STATS["started"] += 1
        USERS.add(message.from_user.id)
        await message.reply("سلام! /help را بزن.")

    @bot.on_message(F.text)
    async def count(message):
        STATS["messages"] += 1
        USERS.add(message.from_user.id)
        if message.text.startswith("/"):
            STATS["commands"][message.text.split()[0]] += 1

    @bot.on_message(F.text == "/admin")
    async def panel(message):
        if not is_admin(message):
            return

        uptime = time.time() - STATS["first_seen"]
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)

        kb = InlineKeyboardBuilder()
        kb.button("📊 آمار کامل", callback_data="admin:stats")
        kb.button("📢 پیام همگانی", callback_data="admin:broadcast")
        kb.button("👥 تعداد کاربران", callback_data="admin:users")
        kb.adjust(1)

        await message.reply(
            f"پنل ادمین\n\n"
            f"مدت اجرا: {hours} ساعت و {minutes} دقیقه\n"
            f"کاربران: {len(USERS)}\n"
            f"پیام‌ها: {STATS['messages']:,}",
            reply_markup=kb.as_markup(),
        )

    @bot.on_callback(F.data == "admin:stats")
    async def stats(callback):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("دسترسی نداری", show_alert=True)
            return

        top = STATS["commands"].most_common(5)
        lines = [
            "آمار:",
            f"  /start زده شده: {STATS['started']}",
            f"  کل پیام: {STATS['messages']:,}",
            f"  کاربر یکتا: {len(USERS)}",
            "",
            "پرتکرارترین دستورها:",
        ]
        lines += [f"  {cmd} — {count}" for cmd, count in top]

        await callback.message.edit_text("\n".join(lines))
        await callback.answer()

    @bot.on_callback(F.data == "admin:users")
    async def users(callback):
        if callback.from_user.id != ADMIN_ID:
            return
        await callback.answer(f"{len(USERS)} کاربر", show_alert=True)

    @bot.on_callback(F.data == "admin:broadcast")
    async def broadcast_prompt(callback):
        if callback.from_user.id != ADMIN_ID:
            return
        await callback.message.edit_text(
            "متن پیام همگانی را بفرست.\n"
            "برای لغو /cancel بزن."
        )
        await callback.answer()

    @bot.on_message(F.text == "/broadcast")
    async def broadcast(message):
        if not is_admin(message):
            return

        text = message.text.replace("/broadcast", "").strip()
        if not text:
            await message.reply("/broadcast متن پیام")
            return

        sent = 0
        failed = 0

        for user_id in list(USERS):
            try:
                await policy.run(bot.send_message, user_id, text)
                sent += 1
            except RateLimitError:
                # سرور گفته صبر کن — صبر می‌کنیم و ادامه می‌دهیم
                await asyncio.sleep(5)
                failed += 1
            except Exception:  # noqa: BLE001
                # کاربر ربات را بلاک کرده، یا حسابش حذف شده
                failed += 1

            # فاصله بین ارسال‌ها تا به flood-wait نخوریم
            await asyncio.sleep(0.05)

        await message.reply(f"ارسال شد: {sent}\nناموفق: {failed}")

    print("پنل ادمین روشن شد. /admin را بزن.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
