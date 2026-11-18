"""تستهای هسته BADKING — بدون توکن و بدون اینترنت."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking import Bot, Dispatcher, F  # noqa: E402
from badking.core.errors import RateLimitError, UnauthorizedError  # noqa: E402
from mock_server import BaleMock  # noqa: E402


def make_bot(mock: BaleMock) -> Bot:
    client = httpx.AsyncClient(transport=mock.transport())
    return Bot("123456:TEST_TOKEN", client=client)


def test_update_parsing():
    from badking.types import Update

    u = Update.model_validate({
        "update_id": 1,
        "message": {
            "message_id": 2, "date": 1700000000,
            "chat": {"id": 123, "type": "private", "first_name": "علی"},
            "from": {"id": 123, "is_bot": False, "first_name": "علی"},
            "text": "سلام",
        },
    })
    assert u.kind == "message"
    assert u.effective_message.text == "سلام"
    assert u.effective_message.from_user.full_name == "علی"


def test_magic_filter():
    class M:
        text = "/start"

    assert (F.text == "/start")(M())
    assert F.text.startswith("/")(M())
    assert (F.text.contains("start"))(M())
    assert not (F.text == "other")(M())


@pytest.mark.asyncio
async def test_get_me():
    mock = BaleMock()
    bot = make_bot(mock)
    me = await bot.get_me()
    assert me.is_bot is True
    assert me.username == "badking_test_bot"
    await bot.close()


@pytest.mark.asyncio
async def test_send_message():
    mock = BaleMock()
    bot = make_bot(mock)
    msg = await bot.send_message(123, "سلام دنیا")
    assert msg.text == "سلام دنیا"
    assert mock.sent[0]["text"] == "سلام دنیا"
    await bot.close()


@pytest.mark.asyncio
async def test_dispatcher_handler():
    mock = BaleMock()
    mock.add_message("/start")
    bot = make_bot(mock)
    dp = Dispatcher()
    got = []

    @dp.message(F.text == "/start")
    async def start(message, bot):
        got.append(message.text)
        await bot.send_message(message.chat.id, "خوش آمدید")

    updates = await bot.get_updates()
    for u in updates:
        await dp.process(u, bot)

    assert got == ["/start"]
    assert mock.sent[0]["text"] == "خوش آمدید"
    await bot.close()


@pytest.mark.asyncio
async def test_error_raises():
    mock = BaleMock()
    bot = make_bot(mock)
    with pytest.raises(UnauthorizedError):
        await bot.request("forceError")
    await bot.close()


@pytest.mark.asyncio
async def test_rate_limit_calibration():
    from badking.core.constants import Limits

    limits = Limits()
    limits.calibrate_from_response(retry_after=3.0, error_code=429)
    assert limits.observed["retry_after_seconds"] == 3
