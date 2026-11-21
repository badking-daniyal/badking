"""Bot API multipart upload — real request-shape assertions.

Official Bale docs: "multipart/form-data (برای آپلود فایل استفاده کنید)" and
"application/json (به جز برای آپلود فایل)". These tests assert the actual
outgoing request, not merely that a method exists.
"""

from __future__ import annotations

import json

import httpx
import pytest

from badking.core.bot import Bot


def _bot_with_capture(captured: dict) -> Bot:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["content_type"] = request.headers.get("content-type", "")
        captured["body"] = request.content
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 1,
                    "date": 1000,
                    "chat": {"id": 5, "type": "private"},
                    "text": "hi",
                },
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return Bot("123:ABC", client=client)


@pytest.mark.asyncio
async def test_send_photo_with_local_file_uses_multipart(tmp_path):
    photo = tmp_path / "pic.jpg"
    photo.write_bytes(b"\xff\xd8\xffJPEGDATA")
    captured: dict = {}
    bot = _bot_with_capture(captured)

    await bot.send_photo(5, str(photo), caption="hello")

    assert captured["method"] == "POST"
    assert captured["url"].endswith("/sendPhoto")
    assert captured["content_type"].startswith("multipart/form-data")
    body = captured["body"]
    assert b"pic.jpg" in body
    assert b"JPEGDATA" in body
    # caption travels as a normal form field
    assert b"hello" in body
    await bot.close()


@pytest.mark.asyncio
async def test_multipart_serializes_reply_markup_as_json(tmp_path):
    doc = tmp_path / "a.txt"
    doc.write_bytes(b"content")
    captured: dict = {}
    bot = _bot_with_capture(captured)

    markup = {"inline_keyboard": [[{"text": "OK", "callback_data": "ok"}]]}
    await bot.send_document(5, str(doc), reply_markup=markup)

    body = captured["body"]
    # The JSON must be a valid, single string value, not a Python repr
    assert b"inline_keyboard" in body
    assert b"{'inline_keyboard'" not in body  # python repr would use single quotes
    # find the json payload inside the multipart body and parse it
    text = body.decode("utf-8", "replace")
    marker = '{"inline_keyboard"'
    idx = text.find(marker)
    assert idx != -1, text[:500]
    end = text.find("\r\n", idx)
    parsed = json.loads(text[idx:end])
    assert parsed == markup
    await bot.close()


@pytest.mark.asyncio
async def test_file_id_stays_json(tmp_path):
    """A file_id is not a local path — the request must stay JSON."""
    captured: dict = {}
    bot = _bot_with_capture(captured)

    await bot.send_photo(5, "AgACAgIAAxkBAAI")

    assert captured["content_type"].startswith("application/json")
    body = json.loads(captured["body"])
    assert body["photo"] == "AgACAgIAAxkBAAI"
    assert body["chat_id"] == 5
    await bot.close()


@pytest.mark.asyncio
async def test_url_stays_json():
    captured: dict = {}
    bot = _bot_with_capture(captured)

    await bot.send_photo(5, "https://example.com/p.jpg")

    assert captured["content_type"].startswith("application/json")
    body = json.loads(captured["body"])
    assert body["photo"] == "https://example.com/p.jpg"
    await bot.close()


@pytest.mark.asyncio
async def test_missing_local_path_is_treated_as_id(tmp_path):
    """A path that does not exist must not crash — it goes as a plain value."""
    captured: dict = {}
    bot = _bot_with_capture(captured)

    await bot.send_photo(5, str(tmp_path / "nope.jpg"))

    assert captured["content_type"].startswith("application/json")
    body = json.loads(captured["body"])
    assert body["photo"].endswith("nope.jpg")
    await bot.close()


@pytest.mark.asyncio
async def test_audio_video_voice_animation_support_local_file(tmp_path):
    for method, api_method, field in (
        ("send_audio", "sendAudio", "audio"),
        ("send_video", "sendVideo", "video"),
        ("send_voice", "sendVoice", "voice"),
        ("send_animation", "sendAnimation", "animation"),
    ):
        f = tmp_path / f"f_{field}.bin"
        f.write_bytes(b"DATA")
        captured: dict = {}
        bot = _bot_with_capture(captured)
        await getattr(bot, method)(5, str(f))
        assert captured["content_type"].startswith("multipart/form-data"), method
        assert captured["url"].endswith(f"/{api_method}")
        assert b"DATA" in captured["body"]
        await bot.close()
