"""ضد اسپم: محدودیت نرخ، فیلتر کلمه، و اخطار.

هدف: گروهی که خودش نظم را نگه می‌دارد، بدون ادمین بیدار.

    python 06_antispam.py
"""

import asyncio
import os
import time
from collections import defaultdict

from badking import Bot, F

# ---------- تنظیمات ----------

MAX_MESSAGES = 5          # در هر پنجره
WINDOW_SECONDS = 10       # طول پنجره
MUTE_MINUTES = 10         # مدت سکوت

BANNED_WORDS = {"کلمه۱", "کلمه۲"}  # کلمات ممنوع را بگذار
BANNED_LINKS = ("bit.ly", "tinyurl.com")  # کوتاه‌کننده‌های لینک


class Tracker:
    """شمارش پیام هر کاربر در پنجره زمانی."""

    def __init__(self) -> None:
        self._hits: dict[int, list[float]] = defaultdict(list)

    def hit(self, user_id: int) -> int:
        """یک پیام ثبت می‌کند و تعداد در پنجره را برمی‌گرداند."""
        now = time.monotonic()
        cutoff = now - WINDOW_SECONDS
        times = [t for t in self._hits[user_id] if t > cutoff]
        times.append(now)
        self._hits[user_id] = times
        return len(times)

    def reset(self, user_id: int) -> None:
        self._hits.pop(user_id, None)


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])
    tracker = Tracker()
    warnings: dict[int, int] = defaultdict(int)

    @bot.on_message(F.text, F.chat.type.in_({"group", "supergroup"}))
    async def guard(message):
        user = message.from_user
        text = (message.text or "").lower()

        # ۱. کلمه ممنوع
        if any(word in text for word in BANNED_WORDS):
            await message.delete()
            await message.reply(f"{user.first_name}، این کلمه مجاز نیست.")
            return

        # ۲. لینک کوتاه‌کننده
        if any(short in text for short in BANNED_LINKS):
            await message.delete()
            await message.reply(f"{user.first_name}، لینک کوتاه‌شده مجاز نیست.")
            return

        # ۳. سرعت ارسال
        count = tracker.hit(user.id)
        if count > MAX_MESSAGES:
            tracker.reset(user.id)
            warnings[user.id] += 1

            if warnings[user.id] >= 3:
                # سومین بار: سکوت
                from datetime import datetime, timedelta

                await bot.restrict_chat_member(
                    message.chat.id,
                    user.id,
                    until_date=datetime.now() + timedelta(minutes=MUTE_MINUTES),
                    can_send_messages=False,
                )
                await message.reply(
                    f"{user.first_name} برای {MUTE_MINUTES} دقیقه ساکت شد."
                )
                warnings[user.id] = 0
            else:
                await message.reply(
                    f"{user.first_name}، آرام‌تر. "
                    f"اخطار {warnings[user.id]} از ۳."
                )

    @bot.on_message(F.text == "/resetwarn")
    async def reset_warn(message):
        if message.reply_to_message:
            warnings[message.reply_to_message.from_user.id] = 0
            tracker.reset(message.reply_to_message.from_user.id)
            await message.reply("اخطارها پاک شد.")

    print("ربات روشن شد. ضد اسپم فعال است.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
