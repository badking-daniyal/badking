"""چند سرور: وضعیت مشترک روی Redis.

هدف: ربات را روی چند سرور اجرا کن، مکالمه کاربر گم نشود.

    python 26_redis.py

نیاز:
    pip install redis
    Redis روشن روی localhost:6379

اگر Redis نداری، همین فایل با SQLite هم کار می‌کند — خط را عوض کن.
"""

import asyncio
import os

from badking import Bot, F, RedisStorage, State, StatesGroup


class Order(StatesGroup):
    item = State()
    address = State()


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    # وضعیت‌ها در Redis، با انقضای یک‌ساعته.
    # اگر کاربر وسط مکالمه رها کند، بعد از یک ساعت خودش پاک می‌شود.
    storage = RedisStorage(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        ttl=3600,
        prefix="shop:",
    )

    await storage.connect()

    if not await storage.health():
        print("Redis جواب نداد. سرویس روشن است؟")
        return

    print(f"Redis وصل شد: {storage}")

    @bot.on_message(F.text == "/order")
    async def start(message):
        key = f"state:{message.from_user.id}"
        await storage.set(key, {"state": Order.item.__name__, "data": {}})
        await message.reply("چه چیزی می‌خواهی؟")

    @bot.on_message(F.text)
    async def step(message):
        key = f"state:{message.from_user.id}"
        current = await storage.get(key)

        if not current:
            return

        state = current.get("state")
        data = current.get("data", {})

        if state == Order.item.__name__:
            data["item"] = message.text
            await storage.set(key, {"state": Order.address.__name__, "data": data})
            await message.reply("آدرس تحویل؟")

        elif state == Order.address.__name__:
            data["address"] = message.text
            await storage.delete(key)
            await message.reply(
                f"سفارش ثبت شد:\n"
                f"  کالا: {data['item']}\n"
                f"  آدرس: {data['address']}"
            )

    @bot.on_message(F.text == "/active")
    async def active(message):
        keys = await storage.keys()
        await message.reply(f"{len(keys)} مکالمه فعال روی این Redis.")

    print("روشن شد. /order را بزن.")
    try:
        await bot.run()
    finally:
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
