"""تست Conversation، KeyboardPaginator و iter_messages."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking.conversation import ConversationManager, ConversationTimeout
from badking.core.bot import Bot
from badking.keyboards import KeyboardPaginator
from badking.types import Update


class FakeBot:
    def __init__(self):
        self.sent: list[tuple[object, str]] = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))
        return {"chat_id": chat_id, "text": text}


def _msg(chat_id: int, text: str):
    return Update.model_validate({
        "update_id": 1,
        "message": {
            "message_id": 1, "date": 1,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": 7, "is_bot": False, "first_name": "x"},
            "text": text,
        },
    })


# ---------- Conversation ----------
def test_conversation_ask_returns_user_message():
    bot = FakeBot()
    mgr = ConversationManager()

    async def scenario():
        async with mgr.conversation(bot, 100) as conv:
            task = asyncio.create_task(conv.ask("اسمت؟", timeout=5))
            await asyncio.sleep(0.01)
            # آپدیت کاربر را به middleware بده
            handled = await mgr(_msg(100, "دانیال"), {}, lambda u, d: _false())
            assert handled is True
            return await task

    reply = asyncio.run(scenario())
    assert reply.text == "دانیال"
    assert bot.sent == [(100, "اسمت؟")]


async def _false():
    return False


def test_conversation_timeout():
    bot = FakeBot()
    mgr = ConversationManager()

    async def scenario():
        async with mgr.conversation(bot, 200) as conv:
            return await conv.get_response(timeout=0.05)

    with pytest.raises(ConversationTimeout):
        asyncio.run(scenario())


def test_conversation_releases_chat_after_exit():
    bot = FakeBot()
    mgr = ConversationManager()

    async def scenario():
        async with mgr.conversation(bot, 300):
            assert mgr.is_active(300) is True
        assert mgr.is_active(300) is False
        # بعد از خروج، آپدیت باید به هندلر عادی برسد
        called = []

        async def next_handler(u, d):
            called.append(1)
            return True

        await mgr(_msg(300, "hi"), {}, next_handler)
        return called

    assert asyncio.run(scenario()) == [1]


def test_conversation_other_chat_not_intercepted():
    bot = FakeBot()
    mgr = ConversationManager()

    async def scenario():
        async with mgr.conversation(bot, 400):
            called = []

            async def next_handler(u, d):
                called.append(1)
                return True

            # چت دیگر باید عبور کند
            await mgr(_msg(999, "hi"), {}, next_handler)
            return called

    assert asyncio.run(scenario()) == [1]


# ---------- KeyboardPaginator ----------
def test_paginator_page_count():
    p = KeyboardPaginator(list(range(12)), per_page=5)
    assert p.page_count == 3
    assert len(p.page_items(0)) == 5
    assert len(p.page_items(2)) == 2


def test_paginator_empty():
    p = KeyboardPaginator([], per_page=5)
    assert p.page_count == 1
    assert p.page_items(0) == []


def test_paginator_markup_nav_buttons():
    p = KeyboardPaginator(["a", "b", "c"], per_page=2, prefix="it")
    m0 = p.markup(0)
    flat0 = [b.text for row in m0.inline_keyboard for b in row]
    assert "بعدی »" in flat0
    assert "« قبلی" not in flat0  # صفحه اول دکمه قبلی ندارد

    m1 = p.markup(1)
    flat1 = [b.text for row in m1.inline_keyboard for b in row]
    assert "« قبلی" in flat1
    assert "بعدی »" not in flat1  # صفحه آخر دکمه بعدی ندارد


def test_paginator_parse():
    p = KeyboardPaginator(["a"], per_page=1, prefix="x")
    assert p.parse("x:page:3") == ("page", 3)
    assert p.parse("x:item:0") == ("item", 0)
    assert p.parse("x:noop:0") is None
    assert p.parse("other:page:1") is None


def test_paginator_custom_labels_and_callback():
    p = KeyboardPaginator(
        [{"n": "کتاب"}], per_page=5,
        label=lambda i: i["n"], callback=lambda i: f"buy:{i['n']}",
    )
    m = p.markup(0)
    btn = m.inline_keyboard[0][0]
    assert btn.text == "کتاب"
    assert btn.callback_data == "buy:کتاب"


def test_paginator_rejects_bad_per_page():
    with pytest.raises(ValueError):
        KeyboardPaginator([], per_page=0)


# ---------- iter_messages ----------
def test_iter_messages_paginates():
    """iter_messages باید صفحه‌به‌صفحه بخواند و تا رسیدن به limit ادامه دهد."""
    calls = []

    def handler(request):
        body = request.content.decode()
        calls.append(body)
        # دو صفحه: اول ۲ پیام، دوم ۱ پیام
        if len(calls) == 1:
            msgs = [
                {"update_id": 101, "message": {"message_id": 10, "date": 1, "chat": {"id": 5, "type": "private"},
                 "from": {"id": 1, "is_bot": False, "first_name": "a"}, "text": "m10"}},
                {"update_id": 102, "message": {"message_id": 9, "date": 1, "chat": {"id": 5, "type": "private"},
                 "from": {"id": 1, "is_bot": False, "first_name": "a"}, "text": "m9"}},
            ]
        else:
            msgs = [
                {"update_id": 103, "message": {"message_id": 8, "date": 1, "chat": {"id": 5, "type": "private"},
                 "from": {"id": 1, "is_bot": False, "first_name": "a"}, "text": "m8"}},
            ]
        return httpx.Response(200, json={"ok": True, "result": msgs})

    bot = Bot("1:X", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    async def collect():
        out = []
        async for m in bot.iter_messages(chat_id=5, limit=3, page_size=2):
            out.append(m.text)
        return out

    texts = asyncio.run(collect())
    assert texts == ["m10", "m9", "m8"]
    assert len(calls) == 2  # دو صفحه خوانده شد
