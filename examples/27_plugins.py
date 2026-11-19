"""افزونه و دو زبان.

هدف: قابلیت اضافه کن بدون دست زدن به هسته؛ پیام‌ها به زبان کاربر.

    python 27_plugins.py
"""

import asyncio
import os

from badking import (
    Bot,
    F,
    LogPlugin,
    Plugin,
    PluginManager,
    StatsPlugin,
    default_translator,
)


class TicketPlugin(Plugin):
    """تیکت ساده — نمونه‌ای از افزونه‌ای که خودت می‌نویسی."""

    name = "tickets"
    version = "1.0.0"

    async def setup(self, bot) -> None:
        self.state["open"] = {}

        @bot.on_message(F.text.startswith("/ticket"))
        async def open_ticket(message):
            text = message.text.replace("/ticket", "").strip()
            if not text:
                await message.reply("موضوع را بنویس: /ticket مشکل ورود")
                return

            ticket_id = len(self.state["open"]) + 1
            self.state["open"][ticket_id] = {
                "user": message.from_user.id,
                "text": text,
            }
            await message.reply(f"تیکت #{ticket_id} ثبت شد.")

    async def teardown(self) -> None:
        self.state["open"].clear()


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    # ---------- افزونه‌ها ----------

    manager = PluginManager()
    manager.register(StatsPlugin())
    manager.register(LogPlugin())
    manager.register(TicketPlugin())

    await manager.setup_all(bot)
    print(f"افزونه‌ها: {manager.names()}")

    # ---------- دو زبان ----------

    t = default_translator()

    @bot.on_message(F.text == "/start")
    async def start(message):
        # زبان کاربر را از جایی بخوان — اینجا ساده نگه می‌داریم
        lang = "fa"
        name = message.from_user.first_name or "دوست"

        await message.reply(t("welcome", name=name, lang=lang))

    @bot.on_message(F.text == "/en")
    async def english(message):
        await message.reply(t("welcome", name="friend", lang="en"))

    @bot.on_message(F.text == "/status")
    async def status(message):
        s = manager.status()
        lines = [f"  {name}: v{info['version']}" for name, info in s.items()]
        await message.reply("افزونه‌ها:\n" + "\n".join(lines))

    # ---------- وصل کردن افزونه‌ها به جریان پیام ----------

    @bot.on_message(F.text)
    async def relay(message):
        await manager.dispatch_message(message)

    print("روشن شد.")
    try:
        await bot.run()
    finally:
        await manager.teardown_all()


if __name__ == "__main__":
    asyncio.run(main())
