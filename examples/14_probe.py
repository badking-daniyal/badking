"""کشف متد ناشناخته: probe و raw_call.

هدف: اگر بله متدی اضافه کرد که ما نمی‌شناسیم، خودت پیدایش کن.

    python 14_probe.py

این کاری است که aiobale نمی‌تواند بکند: اسکیمای RPC در BADKING
قابل کشف و قابل بازنویسی است.
"""

import asyncio

from badking import SelfBot, hybrid_warning
from badking.hybrid.rpc import registry


async def main() -> None:
    print(hybrid_warning())

    # ---------- ۱. چه متدهایی داریم ----------
    print(f"\n{len(registry.names())} متد ثبت‌شده.")
    print("\nسرویس‌ها:")
    services: dict[str, int] = {}
    for name in registry.names():
        service = name.split(".")[0]
        services[service] = services.get(service, 0) + 1
    for service, count in sorted(services.items()):
        print(f"  {service}: {count}")

    # ---------- ۲. جستجو ----------
    print("\nجستجوی 'message':")
    for name in registry.search("message")[:8]:
        print(f"  {name}")

    # ---------- ۳. توصیف یک متد ----------
    print("\nاسکیمای SendMessage:")
    print(registry.describe("SendMessage"))

    # ---------- ۴. فراخوانی خام ----------
    bot = SelfBot(session="badking.session")
    await bot.connect()

    # متدی که در رجیستری نیست، با شماره فیلد خام
    # مثال: SendMessage با فیلدهای ۱ (peer)، ۲ (random_id)، ۳ (text)
    result = await bot.raw_call(
        "SendMessage",
        {
            1: {"_": "Peer", 1: {"_": "User", 1: 123456789, 2: 0}},
            2: 1234567890,
            3: "پیام خام",
        },
    )
    print(f"\nنتیجه raw_call: {result}")

    # ---------- ۵. کاوش ----------
    # probe یک متد را با پارامترهای خالی صدا می‌زند و خطای سرور را می‌خواند
    # تا بفهمد چه فیلدهایی لازم است.
    info = await bot.probe("GetUser")
    print(f"\nنتیجه probe: {info}")

    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
