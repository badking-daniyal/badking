"""تست سبد خرید فروشگاه: اضافه/حذف/جمع کل، به ازای هر کاربر."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "examples"))

from badking import Bot  # noqa: E402
from badking.types import Update  # noqa: E402
from mock_server import BaleMock  # noqa: E402
from importlib import import_module
shop_bot = import_module("22_shop_full")
build_dispatcher = shop_bot.build_dispatcher
cart_text = shop_bot.cart_text
# build_dispatcher, cart_text  # noqa: E402


def cb(data: str, uid: int = 42) -> Update:
    return Update.model_validate({
        "update_id": 1,
        "callback_query": {
            "id": "cb1",
            "from": {"id": uid, "is_bot": False, "first_name": "علی"},
            "data": data,
            "chat_instance": "ci",
            "message": {
                "message_id": 5, "date": 1,
                "chat": {"id": uid, "type": "private"},
                "text": "منو",
            },
        },
    })


def make_bot() -> Bot:
    mock = BaleMock()
    return Bot("1:X", client=httpx.AsyncClient(transport=mock.transport()))


def test_cart_add_and_total():
    async def scenario():
        dp = build_dispatcher()
        bot = make_bot()
        for data in ("add:book", "add:book", "add:coffee"):
            await dp.process(cb(data), bot)
        record = await dp.storage.get("42:42")
        cart = record["data"]["cart"]
        assert cart == {"book": 2, "coffee": 1}
        text = cart_text(cart)
        assert "کتاب پایتون × 2" in text
        assert "جمع کل: 680,000 تومان" in text
        await bot.close()
    asyncio.run(scenario())


def test_cart_remove():
    async def scenario():
        dp = build_dispatcher()
        bot = make_bot()
        await dp.process(cb("add:book"), bot)
        await dp.process(cb("remove:book"), bot)
        record = await dp.storage.get("42:42")
        assert record["data"]["cart"] == {}
        await bot.close()
    asyncio.run(scenario())


def test_cart_per_user_isolated():
    async def scenario():
        dp = build_dispatcher()
        bot = make_bot()
        await dp.process(cb("add:book", uid=1), bot)
        await dp.process(cb("add:coffee", uid=2), bot)
        r1 = await dp.storage.get("1:1")
        r2 = await dp.storage.get("2:2")
        assert r1["data"]["cart"] == {"book": 1}
        assert r2["data"]["cart"] == {"coffee": 1}
        await bot.close()
    asyncio.run(scenario())
