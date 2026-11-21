"""Inline keyboard for SelfBot — protocol-evidence-based tests.

Field numbers are confirmed from aiobale 0.3.9 source:
  types/message_content.py : MessageContent.bot_message=13, TemplateMessage{1,2,5}
  types/inline_keyboard.py : InlineKeyboardMarkup{1:[Row{1:[Button]}]},
                             Button{1:text, 2:{1:url}, 3:{1:callback}, 9:{1:copy}}
These are SOURCE AGREEMENT, not confirmed live Bale server protocol.
"""

from __future__ import annotations

import asyncio

import pytest

from badking.hybrid.client import Peer, SelfBot
from badking.hybrid.proto import decode, encode_named
from badking.hybrid.rpc import make_inline_keyboard, make_text_content
from badking.hybrid.schema import NESTED
from badking.hybrid.session import Session


def test_schema_field_numbers_match_aiobale_source():
    assert NESTED["MessageContent"]["botMessage"] == {
        "field": 13, "fields": "TemplateMessage"
    }
    tm = NESTED["TemplateMessage"]
    assert tm["message"] == {"field": 1, "fields": "MessageContent"}
    assert tm["tempId"] == 2
    assert tm["inlineKeyboardMarkup"] == {"field": 5, "fields": "InlineKeyboard"}
    assert NESTED["InlineKeyboard"]["rows"] == {
        "field": 1, "fields": "InlineKeyboardRow", "repeated": True
    }
    btn = NESTED["InlineButton"]
    assert btn["text"] == 1
    assert btn["url"] == {"field": 2, "fields": "StringValue"}
    assert btn["callbackData"] == {"field": 3, "fields": "StringValue"}
    assert btn["copyText"] == {"field": 9, "fields": "StringValue"}


def test_make_inline_keyboard_normalizes_friendly_names():
    markup = make_inline_keyboard([
        [
            {"text": "بله", "callback_data": "yes"},
            {"text": "سایت", "url": "https://bale.ai"},
        ],
        [{"text": "کپی", "copy_text": "CODE-123"}],
    ])
    rows = markup["inlineKeyboardMarkup"]["rows"]
    assert len(rows) == 2
    assert rows[0]["buttons"][0] == {
        "text": "بله", "callbackData": {"value": "yes"}
    }
    assert rows[0]["buttons"][1] == {
        "text": "سایت", "url": {"value": "https://bale.ai"}
    }
    assert rows[1]["buttons"][0] == {
        "text": "کپی", "copyText": {"value": "CODE-123"}
    }


def test_make_inline_keyboard_backward_compatible_flat_list():
    """نسخههای قبل یک لیست تخت دکمهها را میپذیرفتند — حفظ سازگاری."""
    markup = make_inline_keyboard([{"text": "بلی", "callbackData": "yes"}])
    rows = markup["inlineKeyboardMarkup"]["rows"]
    assert len(rows) == 1
    assert rows[0]["buttons"][0]["text"] == "بلی"


def test_make_inline_keyboard_accepts_schema_names_too():
    markup = make_inline_keyboard([
        [{"text": "x", "callbackData": "raw", "copyText": "c"}]
    ])
    btn = markup["inlineKeyboardMarkup"]["rows"][0]["buttons"][0]
    assert btn["callbackData"] == {"value": "raw"}
    assert btn["copyText"] == {"value": "c"}


@pytest.mark.parametrize("bad", [
    [[{"callback_data": "no-text"}]],
    [[{"text": ""}]],
    [["not a dict"]],
])
def test_make_inline_keyboard_rejects_invalid_buttons(bad):
    with pytest.raises((ValueError, TypeError)):
        make_inline_keyboard(bad)


def test_make_text_content_without_markup_unchanged():
    assert make_text_content("hi") == {"text": {"value": "hi"}}


def test_make_text_content_with_markup_builds_bot_message():
    markup = make_inline_keyboard([[{"text": "ok", "callback_data": "1"}]])
    content = make_text_content("hi", reply_markup=markup, temp_id=42)
    assert "botMessage" in content
    tm = content["botMessage"]
    assert tm["tempId"] == 42
    assert tm["message"] == {"text": {"value": "hi"}}
    assert tm["inlineKeyboardMarkup"] == markup["inlineKeyboardMarkup"]


def test_wire_encoding_field_numbers():
    """Encode a button and verify the actual protobuf wire field numbers.

    The schema here is the RESOLVED form (what RpcSpec.schema() produces),
    built explicitly so this test does not depend on the resolver itself.
    """
    button_schema = {
        "text": 1,
        "url": {"field": 2, "fields": {"value": 1}},
        "callbackData": {"field": 3, "fields": {"value": 1}},
        "copyText": {"field": 9, "fields": {"value": 1}},
    }
    schema = {
        "inlineKeyboardMarkup": {
            "field": 5,
            "fields": {
                "rows": {
                    "field": 1,
                    "fields": {
                        "buttons": {"field": 1, "fields": button_schema, "repeated": True}
                    },
                    "repeated": True,
                }
            },
        }
    }
    payload = {"inlineKeyboardMarkup": {"rows": [
        {"buttons": [{"text": "OK", "callbackData": {"value": "yes"}}]}
    ]}}
    raw = encode_named(payload, schema)
    decoded = decode(raw, {5: {1: {1: {1: None, 3: {1: None}}}}})
    # 5 = inline_keyboard_markup, 1 = rows, 1 = buttons, 1 = text, 3 = callback
    assert 5 in decoded
    markup = decoded[5][0]
    assert 1 in markup
    row = markup[1][0]
    assert 1 in row
    button = row[1][0]
    assert button[1] == [b"OK"]
    assert button[3][0][1] == [b"yes"]


def test_send_message_passes_markup_into_content():
    bot = SelfBot(session=Session(access_token="x", user_id=1))
    captured = {}

    async def fake_get_entity(ref):
        return Peer(id=7, type="user")

    async def fake_call(name, **kwargs):
        captured.update(kwargs)
        return {"seq": 5, "date": 1000}

    bot.get_entity = fake_get_entity
    bot.call = fake_call
    asyncio.get_event_loop().run_until_complete(
        bot.send_message(7, "hi", reply_markup=[[{"text": "b", "callback_data": "1"}]])
    )
    content = captured["content"]
    assert "botMessage" in content
    tm = content["botMessage"]
    assert tm["inlineKeyboardMarkup"]["rows"][0]["buttons"][0]["text"] == "b"


def test_send_message_without_markup_keeps_plain_text():
    bot = SelfBot(session=Session(access_token="x", user_id=1))
    captured = {}

    async def fake_get_entity(ref):
        return Peer(id=7, type="user")

    async def fake_call(name, **kwargs):
        captured.update(kwargs)
        return {"seq": 5, "date": 1000}

    bot.get_entity = fake_get_entity
    bot.call = fake_call
    asyncio.get_event_loop().run_until_complete(bot.send_message(7, "hi"))
    assert captured["content"] == {"text": {"value": "hi"}}
