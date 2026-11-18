"""ربات BADKING — ساختهشده توسط `badking new`"""

import asyncio
import os
from badking import Bot, Dispatcher, F

bot = Bot(os.environ.get("BADKING_TOKEN", "TOKEN"))
dp = Dispatcher()

@dp.message(F.text == "/start")
async def start(message, bot):
    await bot.send_message(message.chat.id, "سلام! من ربات BADKING هستم 🤖")

@dp.message()
async def echo(message, bot):
    if message.text:
        await bot.send_message(message.chat.id, f"شما گفتید: {message.text}")

if __name__ == "__main__":
    asyncio.run(bot.polling(dp))
