"""تست تزریق پارامتر هندلر با اسامی مختلف (بگ، ربات، client...)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking import Bot, Dispatcher, F  # noqa: E402
from badking.types import Update  # noqa: E402


def make_update(text: str) -> Update:
    return Update.model_validate({
        "update_id": 1,
        "message": {
            "message_id": 1, "date": 1,
            "chat": {"id": 1, "type": "private"},
            "from": {"id": 1, "is_bot": False, "first_name": "x"},
            "text": text,
        },
    })


def test_handler_with_b_parameter():
    """همان مشکلی که کاربر دید: async def start(message, b)."""
    calls = []
    dp = Dispatcher()

    @dp.message(F.text == "/start")
    async def start(message, b):
        calls.append(("start", b is not None))

    @dp.message()
    async def echo(message, b):
        calls.append(("echo", b is not None))

    bot = Bot("1:X", client=httpx.AsyncClient())
    asyncio.run(dp.process(make_update("/start"), bot))
    assert calls == [("start", True)]


def test_handler_with_bot_parameter():
    calls = []
    dp = Dispatcher()

    @dp.message()
    async def echo(message, bot):
        calls.append(bot is not None)

    bot = Bot("1:X", client=httpx.AsyncClient())
    asyncio.run(dp.process(make_update("سلام"), bot))
    assert calls == [True]
