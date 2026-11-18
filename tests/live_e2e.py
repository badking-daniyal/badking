"""تست زنده کامل: getMe → getUpdates → ارسال پیام تست به چت خود.

اجرا: py tests/live_e2e.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking import Bot, Dispatcher, F  # noqa: E402
from badking.types import Update  # noqa: E402


def read_token() -> str | None:
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("BADKING_TOKEN="):
                return line.split("=", 1)[1].strip()
    return None


async def main() -> None:
    token = read_token()
    if not token:
        print("توکن پیدا نشد")
        return
    bot = Bot(token)
    me = await bot.get_me()
    print(f"ربات: @{me.username}")

    # 1) خواندن آپدیتها
    updates = await bot.get_updates(timeout=2)
    print(f"آپدیتهای موجود: {len(updates)}")
    for u in updates[:5]:
        print(f"  [{u.update_id}] {u.kind}: {(u.effective_message.content or '')[:40] if u.effective_message else ''}")

    # 2) تست هندلرها با پارامتر b (همان مشکل کاربر)
    dp = Dispatcher()
    got = []

    @dp.message(F.text == "/start")
    async def start(message, b):
        got.append("start")

    @dp.message()
    async def echo(message, b):
        got.append("echo")

    if updates:
        await dp.process(updates[0], bot)
        print(f"هندلر اجرا شد: {got}")

    # 3) ارسال پیام تست به چت اولین کاربر (مسیر کامل sendMessage)
    if updates and updates[0].effective_message:
        chat_id = updates[0].effective_message.chat.id
        try:
            sent = await bot.send_message(chat_id, "✅ تست BADKING: ربات کار میکند.")
            print(f"پیام تست ارسال شد → chat {chat_id}, message_id {sent.message_id}")
        except Exception as e:
            print(f"ارسال ناموفق: {type(e).__name__}: {e}")
    else:
        print("چتی برای ارسال تست پیدا نشد (ربات پیامی نگرفته است).")

    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
