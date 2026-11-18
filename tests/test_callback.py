"""تست هندلرهای دکمه (callback_query)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking import Bot, Dispatcher, F  # noqa: E402
from badking.types import Update  # noqa: E402


def make_callback(data: str) -> Update:
    return Update.model_validate({
        "update_id": 1,
        "callback_query": {
            "id": "cb1",
            "from": {"id": 42, "is_bot": False, "first_name": "علی"},
            "data": data,
            "chat_instance": "ci",
            "message": {
                "message_id": 5, "date": 1,
                "chat": {"id": 42, "type": "private"},
                "text": "منو",
            },
        },
    })


def test_callback_handler_runs():
    got = []
    dp = Dispatcher()

    @dp.callback_query(F.callback_data == "buy:1")
    async def buy(callback_query, bot):
        got.append(("buy", callback_query.data))

    bot = Bot("1:X", client=httpx.AsyncClient())
    asyncio.run(dp.process(make_callback("buy:1"), bot))
    assert got == [("buy", "buy:1")]


def test_callback_does_not_trigger_message_handler():
    got = []
    dp = Dispatcher()

    @dp.message()
    async def msg(message, bot):
        got.append("message")

    @dp.callback_query()
    async def cb(callback_query, bot):
        got.append("callback")

    bot = Bot("1:X", client=httpx.AsyncClient())
    asyncio.run(dp.process(make_callback("x"), bot))
    assert got == ["callback"]


def test_callback_message_access():
    got = []
    dp = Dispatcher()

    @dp.callback_query(F.callback_data.startswith("add:"))
    async def add(callback_query, message, bot):
        got.append((callback_query.data, message.message_id))

    bot = Bot("1:X", client=httpx.AsyncClient())
    asyncio.run(dp.process(make_callback("add:book"), bot))
    assert got == [("add:book", 5)]
