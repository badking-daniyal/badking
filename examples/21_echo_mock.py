"""ربات نمونه BADKING — Echo + /start

بدون توکن هم قابل تست است (با سرور mock)، و با توکن واقعی هم کار میکند.

اجرا:
    # حالت واقعی:
    set BADKING_TOKEN=123456:TOKEN
    python examples/echo_bot.py

    # حالت تست (بدون توکن):
    python examples/echo_bot.py --mock
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking import Bot, Dispatcher, F  # noqa: E402


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    @dp.message(F.text == "/start")
    async def start(message, bot):
        await bot.send_message(message.chat.id, "سلام! من ربات BADKING هستم 🤖\nهر چی بنویسی تکرار میکنم.")

    @dp.message(F.text.startswith("/help"))
    async def help_cmd(message, bot):
        await bot.send_message(message.chat.id, "دستورها: /start , /help")

    @dp.message()
    async def echo(message, bot):
        if message.text:
            await bot.send_message(message.chat.id, f"شما گفتید: {message.text}")

    return dp


async def run_mock() -> None:
    import httpx
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
    from mock_server import BaleMock

    mock = BaleMock()
    mock.add_message("/start")
    mock.add_message("سلام دنیا")
    client = httpx.AsyncClient(transport=mock.transport())
    bot = Bot("123456:MOCK", client=client)
    dp = build_dispatcher()

    updates = await bot.get_updates()
    for u in updates:
        await dp.process(u, bot)

    print("--- پیامهای ارسالشده توسط ربات (mock) ---")
    for sent in mock.sent:
        print(" →", sent["text"])
    await bot.close()


async def run_real() -> None:
    token = os.environ.get("BADKING_TOKEN")
    if not token:
        print("لطفاً BADKING_TOKEN رو تنظیم کن یا از --mock استفاده کن.")
        return
    bot = Bot(token)
    dp = build_dispatcher()
    print("ربات در حال اجرا... (Ctrl+C برای توقف)")
    await bot.polling(dp)


if __name__ == "__main__":
    if "--mock" in sys.argv:
        asyncio.run(run_mock())
    else:
        asyncio.run(run_real())
