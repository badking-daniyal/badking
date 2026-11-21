"""تست‌های مستقل صحت Client API: pagination، parsing، schema.

این تست‌ها رفتار *مشاهده‌شده* را میسنجند، نه اینکه فقط وجود یک متد را
تأیید کنند. هرجا رفتار به پروتکل واقعی بله وابسته است، از fixtureهای
ساختاریافته‌ای استفاده میشود که شکل دقیق داده را نشان میدهند.

شاهد ساختار: aiobale 0.3.9 (types/message_content.py، service_message.py،
service_ext.py، gift_packet.py) — منبع مقایسه، نه اثبات پروتکل رسمی.
"""

from __future__ import annotations

import asyncio

import pytest

from badking.hybrid.client import Dialog, Message, Peer, SelfBot
from badking.hybrid.proto import decode, encode_named
from badking.hybrid.schema import NESTED
from badking.hybrid.rpc import registry as default_registry
from badking.hybrid.rpc import _resolve, _to_field_schema


def _wire_schema(named: dict) -> dict:
    """تبدیل schema نام‌دار به schema شماره‌دار برای decode."""
    return _to_field_schema(named)


def _resolved(named: dict) -> dict:
    """حل ارجاع‌های نوعی (مثل "ServiceMessage") برای encode_named."""
    return {k: _resolve(v) for k, v in named.items()}


# --------------------------------------------------------------------------
# ابزارهای کمکی
# --------------------------------------------------------------------------


def _bot() -> SelfBot:
    bot = SelfBot(session=None)
    bot._my_id = 100
    return bot


def _peer(pid: int = 5, ptype: int = 2) -> dict:
    return {"type": ptype, "id": pid, "accessHash": 777}


def _text_message(msg_id: int, date: float, text: str, sender: int = 200) -> dict:
    return {
        "senderId": sender,
        "messageId": msg_id,
        "date": date,
        "content": {"text": {"value": text}},
    }


class _PagedBot(SelfBot):
    """کلاینتی که ``call`` را با صفحه‌های آماده پاسخ می‌دهد.

    صفحه‌ها بهترتیب برگردانده میشوند؛ اگر صفحه‌ها تمام شوند، آخرین صفحه
    تکرار می‌شود (سناریوی سروری که cursor را تکرار می‌کند).
    """

    def __init__(self, pages, repeat_last: bool = True):
        super().__init__(session=None)
        self._my_id = 100
        self._pages = list(pages)
        self._repeat_last = repeat_last
        self.calls: list[dict] = []

    async def call(self, name, **kwargs):
        self.calls.append({"name": name, **kwargs})
        if not self._pages:
            return {}
        if len(self._pages) == 1:
            return self._pages[0]
        return self._pages.pop(0)


# --------------------------------------------------------------------------
# ۱) iter_dialogs — صفحه‌بندی
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iter_dialogs_first_request_uses_zero_offset():
    """اولین درخواست باید offset_date=0 و limit=batch باشد."""
    bot = _PagedBot([{"dialogs": []}])
    _ = [d async for d in bot.iter_dialogs(batch=25)]
    assert bot.calls[0]["name"] == "messaging.LoadDialogs"
    assert bot.calls[0]["offset_date"] == 0
    assert bot.calls[0]["limit"] == 25


@pytest.mark.asyncio
async def test_iter_dialogs_next_page_cursor_is_last_sort_date():
    """مکان‌نمای صفحه بعد باید sortDate آخرین ردیف صفحه قبل باشد."""
    page1 = {
        "dialogs": [
            {"peer": _peer(1), "sortDate": 900, "unreadCount": 3},
            {"peer": _peer(2), "sortDate": 800},
        ]
    }
    page2 = {"dialogs": [{"peer": _peer(3), "sortDate": 700}]}
    bot = _PagedBot([page1, page2])
    dialogs = [d async for d in bot.iter_dialogs(batch=2)]
    assert len(dialogs) == 3
    assert bot.calls[1]["offset_date"] == 800


@pytest.mark.asyncio
async def test_iter_dialogs_does_not_use_row_count_as_cursor():
    """تعداد ردیف نباید بهعنوان cursor استفاده شود.

    سرور ۲ ردیف برمیگرداند ولی sortDate=900 است؛ cursor باید 900 باشد
    نه 2 (تعداد ردیف) و نه 800.
    """
    page = {"dialogs": [{"peer": _peer(1), "sortDate": 900}]}
    bot = _PagedBot([page, page])
    _ = [d async for d in bot.iter_dialogs(batch=50)]
    assert bot.calls[1]["offset_date"] == 900


@pytest.mark.asyncio
async def test_iter_dialogs_empty_page_ends_iteration():
    bot = _PagedBot([{"dialogs": []}])
    dialogs = [d async for d in bot.iter_dialogs()]
    assert dialogs == []
    assert len(bot.calls) == 1


@pytest.mark.asyncio
async def test_iter_dialogs_missing_dialogs_key_ends_iteration():
    """پاسخ ناقص (بدون کلید dialogs) نباید crash کند."""
    bot = _PagedBot([{}])
    dialogs = [d async for d in bot.iter_dialogs()]
    assert dialogs == []


@pytest.mark.asyncio
async def test_iter_dialogs_malformed_row_does_not_crash():
    """ردیف خراب (غیر dict) نباید کل پیمایش را از کار بیندازد."""
    page = {"dialogs": ["not-a-dict", {"peer": _peer(9), "sortDate": 500}]}
    bot = _PagedBot([page, {"dialogs": []}])
    dialogs = [d async for d in bot.iter_dialogs(batch=2)]
    assert len(dialogs) == 2
    assert dialogs[0].peer.id == 0  # ردیف خراب → peer خالی
    assert dialogs[1].peer.id == 9


@pytest.mark.asyncio
async def test_iter_dialogs_duplicate_dialog_across_pages_is_not_repeated():
    """گفتگوی تکراری بین صفحات نباید دوباره تحویل داده شود."""
    dup = {"peer": _peer(1), "sortDate": 900}
    page1 = {"dialogs": [dup]}
    page2 = {"dialogs": [dup, {"peer": _peer(2), "sortDate": 800}]}
    bot = _PagedBot([page1, page2, {"dialogs": []}])
    dialogs = [d async for d in bot.iter_dialogs(batch=1)]
    ids = [d.peer.id for d in dialogs]
    assert ids == [1, 2]


@pytest.mark.asyncio
async def test_iter_dialogs_same_id_different_type_is_not_duplicate():
    """کلید یکتا (نوع, شناسه) است؛ شناسه یکسان با نوع متفاوت جداست."""
    page1 = {"dialogs": [{"peer": _peer(42, ptype=2), "sortDate": 900}]}
    page2 = {"dialogs": [{"peer": _peer(42, ptype=4), "sortDate": 800}]}
    bot = _PagedBot([page1, page2, {"dialogs": []}])
    dialogs = [d async for d in bot.iter_dialogs(batch=1)]
    assert len(dialogs) == 2
    assert dialogs[0].peer.type == "chat"
    assert dialogs[1].peer.type == "channel"


@pytest.mark.asyncio
async def test_iter_dialogs_stops_when_cursor_repeats():
    """سروری که همان cursor را برمیگرداند نباید حلقه بینهایت بسازد."""
    page = {"dialogs": [{"peer": _peer(1), "sortDate": 500}]}
    bot = _PagedBot([page])
    dialogs = [d async for d in bot.iter_dialogs(batch=1)]
    assert len(bot.calls) == 2
    assert len(dialogs) == 1


@pytest.mark.asyncio
async def test_iter_dialogs_short_page_still_continues():
    """صفحه کوتاه‌تر از limit لزوماً پایان نیست.

    سرور ممکن است کمتر از limit برگرداند ولی داده بیشتری داشته باشد؛
    پیمایش باید با cursor معتبر ادامه یابد.
    """
    page1 = {"dialogs": [{"peer": _peer(1), "sortDate": 900}]}
    page2 = {"dialogs": [{"peer": _peer(2), "sortDate": 800}]}
    bot = _PagedBot([page1, page2, {"dialogs": []}])
    dialogs = [d async for d in bot.iter_dialogs(batch=50)]
    assert [d.peer.id for d in dialogs] == [1, 2]


@pytest.mark.asyncio
async def test_iter_dialogs_respects_limit():
    page = {"dialogs": [{"peer": _peer(i), "sortDate": 1000 - i} for i in range(10)]}
    bot = _PagedBot([page, {"dialogs": []}])
    dialogs = [d async for d in bot.iter_dialogs(limit=3, batch=10)]
    assert len(dialogs) == 3


@pytest.mark.asyncio
async def test_iter_dialogs_network_error_propagates():
    """خطای شبکه باید به کاربر برسد، نه اینکه بیصدا پایان یابد."""
    bot = _PagedBot([{"dialogs": []}])

    async def boom(name, **kwargs):
        raise ConnectionError("network down")

    bot.call = boom
    with pytest.raises(ConnectionError):
        _ = [d async for d in bot.iter_dialogs()]


@pytest.mark.asyncio
async def test_iter_dialogs_timeout_propagates():
    bot = _PagedBot([{"dialogs": []}])

    async def timeout(name, **kwargs):
        raise asyncio.TimeoutError()

    bot.call = timeout
    with pytest.raises(asyncio.TimeoutError):
        _ = [d async for d in bot.iter_dialogs()]


@pytest.mark.asyncio
async def test_iter_dialogs_cancellation_propagates():
    """لغو کورسین باید متوقف شود و پیام CancelledError بالا برود."""
    bot = _PagedBot([{"dialogs": [{"peer": _peer(1), "sortDate": 900}]}])
    started = asyncio.Event()

    async def slow_call(name, **kwargs):
        started.set()
        await asyncio.sleep(10)
        return {"dialogs": []}

    bot.call = slow_call

    async def run():
        async for _ in bot.iter_dialogs():
            pass

    task = asyncio.create_task(run())
    # محدودیت زمانی صریح: اگر call هرگز صدا زده نشود، تست بهجای
    # گیر کردن بیانتها، با TimeoutError مشخص شکست میخورد.
    await asyncio.wait_for(started.wait(), timeout=2.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# --------------------------------------------------------------------------
# ۲) iter_messages — صفحه‌بندی و مرز صفحات
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iter_messages_first_request_uses_minus_one_offset():
    bot = _PagedBot([{"data": []}])
    _ = [m async for m in bot.iter_messages(5, batch=10)]
    assert bot.calls[0]["name"] == "messaging.LoadHistory"
    assert bot.calls[0]["offset_date"] == -1
    assert bot.calls[0]["limit"] == 10
    assert bot.calls[0]["load_mode"] == 2


@pytest.mark.asyncio
async def test_iter_messages_boundary_has_no_gap_or_duplicate():
    """مرز صفحات: نه پیام گم میشود نه تکرار."""
    page1 = {"data": [_text_message(3, 300, "c"), _text_message(2, 200, "b")]}
    page2 = {"data": [_text_message(1, 100, "a")]}
    bot = _PagedBot([page1, page2, {"data": []}])
    msgs = [m async for m in bot.iter_messages(5, batch=2)]
    assert [m.id for m in msgs] == [3, 2, 1]
    assert len({m.id for m in msgs}) == 3


@pytest.mark.asyncio
async def test_iter_messages_cursor_moves_to_oldest_date():
    """مکان‌نمای بعدی = قدیمی‌ترین تاریخ صفحه قبل."""
    page1 = {"data": [_text_message(5, 500, "e"), _text_message(4, 400, "d")]}
    page2 = {"data": [_text_message(3, 300, "c")]}
    bot = _PagedBot([page1, page2, {"data": []}])
    _ = [m async for m in bot.iter_messages(5, batch=2)]
    assert bot.calls[1]["offset_date"] == 400


@pytest.mark.asyncio
async def test_iter_messages_duplicate_across_pages_is_dropped():
    """پیام تکراری بین صفحات یکبار تحویل داده میشود."""
    dup = _text_message(7, 700, "dup")
    page1 = {"data": [dup]}
    page2 = {"data": [dup, _text_message(6, 600, "six")]}
    bot = _PagedBot([page1, page2, {"data": []}])
    msgs = [m async for m in bot.iter_messages(5, batch=1)]
    assert [m.id for m in msgs] == [7, 6]


@pytest.mark.asyncio
async def test_iter_messages_fully_duplicate_page_does_not_stop_early():
    """صفحه تماماً تکراری نباید پیمایش را زود قطع کند.

    رگرسیون: قبلاً اگر همه پیام‌های صفحه تکراری بودند، ``page`` خالی
    میشد و ``oldest`` به None میرسید → پیمایش همان‌جا میشد، درحالی‌که
    سرور داده جدید داشت.
    """
    dup = _text_message(7, 700, "dup")
    page1 = {"data": [dup]}
    page2 = {"data": [dup]}  # همان پیام دوباره
    page3 = {"data": [_text_message(6, 600, "new")]}
    bot = _PagedBot([page1, page2, page3, {"data": []}])
    msgs = [m async for m in bot.iter_messages(5, batch=1)]
    assert [m.id for m in msgs] == [7, 6]


@pytest.mark.asyncio
async def test_iter_messages_zero_message_id_is_not_treated_as_duplicate():
    """پیام بدون شناسه نباید بهاشتباه تکراری حذف شود."""
    page1 = {"data": [{"senderId": 1, "date": 100, "content": {"text": {"value": "a"}}}]}
    page2 = {"data": [{"senderId": 1, "date": 90, "content": {"text": {"value": "b"}}}]}
    bot = _PagedBot([page1, page2, {"data": []}])
    msgs = [m async for m in bot.iter_messages(5, batch=1)]
    assert [m.text for m in msgs] == ["a", "b"]


@pytest.mark.asyncio
async def test_iter_messages_empty_response_ends_iteration():
    bot = _PagedBot([{"data": []}])
    msgs = [m async for m in bot.iter_messages(5)]
    assert msgs == []


@pytest.mark.asyncio
async def test_iter_messages_missing_data_key_ends_iteration():
    bot = _PagedBot([{}])
    msgs = [m async for m in bot.iter_messages(5)]
    assert msgs == []


@pytest.mark.asyncio
async def test_iter_messages_reverse_flips_page_order():
    page1 = {"data": [_text_message(3, 300, "c"), _text_message(2, 200, "b")]}
    page2 = {"data": [_text_message(1, 100, "a")]}
    bot = _PagedBot([page1, page2, {"data": []}])
    msgs = [m async for m in bot.iter_messages(5, batch=2, reverse=True)]
    assert [m.id for m in msgs] == [2, 3, 1]


@pytest.mark.asyncio
async def test_iter_messages_respects_limit():
    page = {"data": [_text_message(i, i * 100, str(i)) for i in range(10)]}
    bot = _PagedBot([page, {"data": []}])
    msgs = [m async for m in bot.iter_messages(5, limit=5, batch=10)]
    assert len(msgs) == 5


@pytest.mark.asyncio
async def test_iter_messages_network_error_propagates():
    bot = _PagedBot([{"data": []}])

    async def boom(name, **kwargs):
        raise ConnectionError("network down")

    bot.call = boom
    with pytest.raises(ConnectionError):
        _ = [m async for m in bot.iter_messages(5)]


@pytest.mark.asyncio
async def test_iter_messages_timeout_propagates():
    bot = _PagedBot([{"data": []}])

    async def timeout(name, **kwargs):
        raise asyncio.TimeoutError()

    bot.call = timeout
    with pytest.raises(asyncio.TimeoutError):
        _ = [m async for m in bot.iter_messages(5)]


@pytest.mark.asyncio
async def test_iter_messages_cancellation_propagates():
    bot = _PagedBot([{"data": [_text_message(1, 100, "a")]}])
    started = asyncio.Event()
    got: list[int] = []

    async def slow_call(name, **kwargs):
        started.set()
        await asyncio.sleep(10)
        return {"data": []}

    bot.call = slow_call

    async def run():
        # ref الزامی است؛ بدون آن get_entity صدا زده نمیشود و
        # slow_call هرگز اجرا نمیشد (علت گیر کردن تست).
        async for m in bot.iter_messages(5):
            got.append(m.id)

    task = asyncio.create_task(run())
    # محدودیت زمانی صریح: اگر call هرگز صدا زده نشود، تست بهجای
    # گیر کردن بیانتها، با TimeoutError مشخص شکست میخورد.
    await asyncio.wait_for(started.wait(), timeout=2.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# --------------------------------------------------------------------------
# ۳) Message parsing — همه انواع محتوا
# --------------------------------------------------------------------------


def test_parse_message_text_content():
    bot = _bot()
    msg = bot._parse_message(_text_message(11, 1234.5, "سلام"), Peer(id=5))
    assert msg.id == 11
    assert msg.text == "سلام"
    assert msg.sender_id == 200
    assert msg.date == 1234.5
    assert msg.content_type == "text"
    assert msg.is_edited is False
    assert msg.reply_to_id is None


def test_parse_message_document_content_keeps_caption():
    """پیام سند باید کپشنش حفظ شود، نه اینکه متن خالی شود."""
    bot = _bot()
    raw = {
        "senderId": 1,
        "messageId": 12,
        "date": 10,
        "content": {
            "document": {
                "fileId": 555,
                "accessHash": 999,
                "size": 1024,
                "name": "a.pdf",
                "mimeType": "application/pdf",
                "caption": {"content": "توضیح فایل"},
            }
        },
    }
    msg = bot._parse_message(raw, Peer(id=5))
    assert msg.content_type == "document"
    assert msg.text == "توضیح فایل"
    assert msg.media_info()["file_id"] == 555
    assert msg.media_info()["name"] == "a.pdf"


def test_parse_message_service_content():
    """پیام سرویس (عضویت/خروج) باید متنش حفظ شود."""
    bot = _bot()
    raw = {
        "senderId": 0,
        "messageId": 13,
        "date": 20,
        "content": {"serviceMessage": {"text": "علی به گروه اضافه شد", "ext": {}}},
    }
    msg = bot._parse_message(raw, Peer(id=5))
    assert msg.content_type == "service"
    assert msg.text == "علی به گروه اضافه شد"
    assert msg.is_service is True


def test_parse_message_bot_content_reads_inner_message():
    """پیام ربات: متن از TemplateMessage.message خوانده میشود."""
    bot = _bot()
    raw = {
        "senderId": 0,
        "messageId": 14,
        "date": 30,
        "content": {
            "botMessage": {
                "tempId": 1,
                "message": {"text": {"value": "پاسخ ربات"}},
            }
        },
    }
    msg = bot._parse_message(raw, Peer(id=5))
    assert msg.content_type == "bot"
    assert msg.text == "پاسخ ربات"


def test_parse_message_gift_content():
    bot = _bot()
    raw = {
        "senderId": 0,
        "messageId": 15,
        "date": 40,
        "content": {"gift": {"count": 2, "totalAmount": 100, "message": {"value": "هدیه"}}},
    }
    msg = bot._parse_message(raw, Peer(id=5))
    assert msg.content_type == "gift"
    assert msg.text == "هدیه"


def test_parse_message_empty_content():
    bot = _bot()
    raw = {"senderId": 0, "messageId": 16, "date": 50, "content": {"empty": True}}
    msg = bot._parse_message(raw, Peer(id=5))
    assert msg.content_type == "empty"
    assert msg.is_forwarded is True
    assert msg.text == ""


def test_parse_message_unknown_content_keeps_raw():
    """محتوای ناشناخته نباید حذف شود؛ raw باید دست‌نخورده بماند."""
    bot = _bot()
    raw = {
        "senderId": 0,
        "messageId": 17,
        "date": 60,
        "content": {"somethingNew": {"x": 1}},
    }
    msg = bot._parse_message(raw, Peer(id=5))
    assert msg.content_type == "unknown"
    assert msg.raw["content"]["somethingNew"] == {"x": 1}


def test_parse_message_missing_content_is_safe():
    bot = _bot()
    msg = bot._parse_message({"messageId": 18, "date": 70}, Peer(id=5))
    assert msg.text == ""
    assert msg.content_type == "unknown"
    assert msg.id == 18


def test_parse_message_non_dict_is_safe():
    bot = _bot()
    msg = bot._parse_message("garbage", Peer(id=5))
    assert msg.id == 0
    assert msg.text == ""


def test_parse_message_reply_and_edited():
    bot = _bot()
    raw = {
        "senderId": 200,
        "messageId": 19,
        "date": 80,
        "editedAt": 95,
        "repliedTo": {"messageId": 3, "senderId": 100, "date": 70},
        "content": {"text": {"value": "پاسخ"}},
    }
    msg = bot._parse_message(raw, Peer(id=5))
    assert msg.reply_to_id == 3
    assert msg.is_edited is True
    assert msg.edited_at == 95.0


def test_parse_message_is_out_flag():
    bot = _bot()
    mine = bot._parse_message(_text_message(20, 1, "من", sender=100), Peer(id=5))
    other = bot._parse_message(_text_message(21, 1, "او", sender=200), Peer(id=5))
    assert mine.is_out is True
    assert other.is_out is False


def test_parse_message_bytes_text_is_decoded():
    bot = _bot()
    raw = {"messageId": 22, "date": 1, "content": {"text": {"value": b"bytes"}}}
    msg = bot._parse_message(raw, Peer(id=5))
    assert msg.text == "bytes"


# --------------------------------------------------------------------------
# ۴) Dialog parsing
# --------------------------------------------------------------------------


def test_parse_dialog_reads_peer_title_and_unread():
    bot = _bot()
    raw = {
        "peer": {"type": 3, "id": 88, "accessHash": 5, "title": "گروه من", "username": "g"},
        "unreadCount": 12,
        "sortDate": 1700,
        "content": {"text": {"value": "آخرین پیام"}},
    }
    dlg = bot._parse_dialog(raw)
    assert dlg.peer.id == 88
    assert dlg.peer.type == "group"
    assert dlg.peer.title == "گروه من"
    assert dlg.peer.username == "g"
    assert dlg.unread == 12
    assert dlg.last_message == "آخرین پیام"
    assert dlg.last_date == 1700.0
    assert dlg.title == "گروه من"


def test_parse_dialog_document_last_message():
    """آخرین پیام سندی هم باید متن قابل‌استخراج داشته باشد."""
    bot = _bot()
    raw = {
        "peer": {"type": 2, "id": 9},
        "sortDate": 5,
        "content": {"document": {"fileId": 1, "name": "x.txt", "caption": {"content": "کپ"}}},
    }
    dlg = bot._parse_dialog(raw)
    assert dlg.last_message == "کپ"


def test_parse_dialog_malformed_is_safe():
    bot = _bot()
    dlg = bot._parse_dialog({"peer": "not-a-dict"})
    assert dlg.peer.id == 0
    assert dlg.unread == 0


# --------------------------------------------------------------------------
# ۵) Response Schema — ساختار واقعی روی wire
# --------------------------------------------------------------------------


def test_message_content_schema_field_numbers_match_source():
    """شماره فیلدهای MessageContent باید با سورس مرجع یکی باشد.

    شاهد: aiobale 0.3.9 types/message_content.py
      document=4, empty=5, serviceMessage=11, botMessage=13, text=15, gift=17
    """
    content = NESTED["MessageContent"]
    assert content["document"] == {"field": 4, "fields": "DocumentMessage"}
    assert content["empty"] == 5
    assert content["serviceMessage"] == {"field": 11, "fields": "ServiceMessage"}
    assert content["botMessage"] == {"field": 13, "fields": "TemplateMessage"}
    assert content["text"] == {"field": 15, "fields": {"value": 1}}
    assert content["gift"] == {"field": 17, "fields": "GiftPacket"}


def test_service_message_schema_field_numbers():
    """شاهد: aiobale 0.3.9 types/service_message.py → text=1, ext=2."""
    svc = NESTED["ServiceMessage"]
    assert svc["text"] == 1
    assert svc["ext"] == {"field": 2, "fields": "ServiceExt"}


def test_service_ext_schema_field_numbers():
    """شاهد: aiobale 0.3.9 types/service_ext.py → giftOpened=18."""
    assert NESTED["ServiceExt"]["giftOpened"] == {"field": 18, "fields": "GiftOpened"}
    assert NESTED["GiftOpened"] == {
        "userId": 1,
        "othersCount": 2,
        "messageId": 3,
        "messageDate": 4,
    }


def test_gift_packet_schema_field_numbers():
    """شاهد: aiobale 0.3.9 types/gift_packet.py."""
    gift = NESTED["GiftPacket"]
    assert gift["count"] == 1
    assert gift["totalAmount"] == 2
    assert gift["givingType"] == 3
    assert gift["token"] == {"field": 4, "fields": "StringValue"}
    assert gift["message"] == {"field": 5, "fields": "StringValue"}
    assert gift["ownerId"] == 6
    assert gift["showAmounts"] == {"field": 7, "fields": "BoolValue"}


def test_message_data_schema_has_structured_reply_and_neighbours():
    """repliedTo/previousMessage/nextMessage ساختار دارند نه scalar."""
    md = NESTED["MessageData"]
    assert md["repliedTo"] == {"field": 8, "fields": "QuotedMessage"}
    assert md["previousMessage"] == {"field": 10, "fields": "MessageData"}
    assert md["nextMessage"] == {"field": 11, "fields": "MessageData"}
    assert md["editedAt"] == 12


def test_service_message_roundtrip_on_wire():
    """رمزگذاری/رمزگشایی واقعی ServiceMessage روی wire."""
    payload = encode_named(
        {"text": "عضو جدید", "ext": {}},
        _resolved(NESTED["ServiceMessage"]),
    )
    decoded = decode(payload, _wire_schema(NESTED["ServiceMessage"]))
    # decode خام، رشتهها را بهعنوان bytes برمیگرداند (رفتار صحیح
    # wire-level پروتوباف)؛ باینر را میسنجیم نه str.
    assert decoded[1] == ["عضو جدید".encode("utf-8")]


def test_gift_packet_roundtrip_on_wire():
    payload = encode_named(
        {"count": 3, "totalAmount": 500, "message": {"value": "هدیه"}},
        _resolved(NESTED["GiftPacket"]),
    )
    decoded = decode(payload, _wire_schema(NESTED["GiftPacket"]))
    assert decoded[1] == [3]
    assert decoded[2] == [500]
    # فیلد 5 (StringValue) بهصورت تودرتو رمزگشایی میشود: {1: [bytes]}.
    assert decoded[5] == [{1: ["هدیه".encode("utf-8")]}]


def test_message_content_roundtrip_preserves_all_variants():
    """همه انواع محتوا باید روی wire بدون افت رفت‌وبرگشت کنند."""
    content_schema = _resolved(NESTED["MessageContent"])
    wire = _wire_schema(NESTED["MessageContent"])
    for payload_dict in (
        {"text": {"value": "hi"}},
        {"empty": True},
        {"serviceMessage": {"text": "svc", "ext": {}}},
        {"botMessage": {"tempId": 1, "message": {"text": {"value": "bot"}}}},
        {"document": {"fileId": 1, "accessHash": 2, "size": 3}},
        {"gift": {"count": 1, "totalAmount": 2}},
    ):
        payload = encode_named(payload_dict, content_schema)
        decoded = decode(payload, wire)
        assert decoded, f"decode خالی برای {payload_dict}"


def test_load_history_response_schema_decodes_messages():
    """LoadHistory باید پیام‌ها را با ساختار درست برگرداند."""
    spec = default_registry.get("messaging.LoadHistory")
    assert spec is not None
    named = _resolved(spec.schema_for_naming())
    payload = encode_named(
        {"data": [_text_message(1, 100, "سلام")]},
        named,
    )
    decoded = decode(payload, spec.resp_schema())
    assert decoded[1], "هیچ پیامی رمزگشایی نشد"
