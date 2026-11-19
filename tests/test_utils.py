"""تست enums، utils، keyboard builder و CallbackData — همه آفلاین."""

from __future__ import annotations

import pytest

from badking.enums import (
    AuthErrors,
    ChatType,
    GiftOpenning,
    GiftOpening,
    GivingType,
    GroupType,
    ListLoadMode,
    PeerSource,
    PeerType,
    PrivacyMode,
    ReportKind,
    Restriction,
    SendCodeType,
    SendType,
    TypingMode,
)
from badking.keyboards import (
    InlineKeyboardBuilder,
    KeyboardPaginator,
    ReplyKeyboardBuilder,
)
from badking.utils import (
    Throttle,
    create_progress_bar,
    decode_int64_list,
    encode_int64_list,
    extract_join_token,
    extract_username,
    format_bytes,
    generate_id,
    normalize_phone,
    random_id,
    smart_split_text,
    split_by_length,
    to_english_digits,
    to_persian_digits,
)
from badking.utils.callback_data import CallbackData, CallbackFilter


# ---------- enums ----------

class TestEnums:
    def test_peer_type(self):
        assert PeerType.PRIVATE == 1
        assert PeerType.GROUP == 2
        assert PeerType.UNKNOWN == 0

    def test_chat_type(self):
        assert ChatType.PRIVATE == 1
        assert ChatType.SUPER_GROUP == 5

    def test_group_type(self):
        assert GroupType.GROUP == 0
        assert GroupType.CHANNEL == 1

    def test_load_mode(self):
        assert ListLoadMode.FORWARD == 1
        assert ListLoadMode.BACKWARD == 2

    def test_typing_mode(self):
        assert TypingMode.TEXT == 1
        assert TypingMode.SENDINGPHOTO == 5
        assert TypingMode.CHOOSINGEMOJI == 12
        # نام‌های جایگزین همان مقدار را می‌دهند
        assert TypingMode.CHOSINGGIF == TypingMode.CHOOSINGGIF == 9

    def test_send_type(self):
        assert SendType.PHOTO == 1
        assert SendType.DOCUMENT == 6

    def test_send_code_type(self):
        assert SendCodeType.SMS == 3
        assert SendCodeType.TELEGRAM_GATEWAY == 12

    def test_auth_errors(self):
        assert AuthErrors.WRONG_CODE == 3
        assert AuthErrors.SIGN_UP_NEEDED == 5

    def test_gift_aliases(self):
        assert GiftOpening is GiftOpenning
        assert GiftOpenning.SUCCESSFUL == 3

    def test_others(self):
        assert PrivacyMode.SPAM == 2
        assert Restriction.PUBLIC == 1
        assert ReportKind.FALSE_INFORMATION == 6
        assert GivingType.RANDOM == 1
        assert PeerSource.MARKET == 3

    def test_int_conversion(self):
        assert int(PeerType.GROUP) == 2
        assert PeerType(1) is PeerType.PRIVATE


# ---------- متن ----------

class TestText:
    def test_short_text_unchanged(self):
        assert smart_split_text("سلام") == ["سلام"]

    def test_empty(self):
        assert smart_split_text("") == [""]

    def test_splits_at_newline(self):
        text = "a" * 50 + "\n" + "b" * 50
        parts = smart_split_text(text, max_length=60)
        assert len(parts) == 2
        assert all(len(p) <= 60 for p in parts)
        assert parts[0] == "a" * 50

    def test_splits_at_space(self):
        text = "word " * 100
        parts = smart_split_text(text, max_length=50)
        assert all(len(p) <= 50 for p in parts)
        assert "".join(p.replace(" ", "") for p in parts) == text.replace(" ", "")

    def test_hard_cut_when_no_whitespace(self):
        text = "x" * 250
        parts = smart_split_text(text, max_length=100)
        assert len(parts) == 3
        assert all(len(p) <= 100 for p in parts)

    def test_no_content_lost(self):
        text = "کلمه " * 500
        parts = smart_split_text(text, max_length=200)
        rejoined = "".join(parts).replace(" ", "")
        assert rejoined == text.replace(" ", "")

    def test_split_by_length(self):
        parts = split_by_length("abcdefghij", 4)
        assert parts == ["abcd", "efgh", "ij"]

    def test_split_by_length_empty(self):
        assert split_by_length("") == [""]


# ---------- شناسه ----------

class TestId:
    def test_length(self):
        for n in (1, 5, 16):
            assert len(str(generate_id(n))) == n

    def test_no_leading_zero(self):
        for _ in range(50):
            assert str(generate_id(10))[0] != "0"

    def test_positive(self):
        assert generate_id(16) > 0

    def test_invalid_length(self):
        with pytest.raises(ValueError):
            generate_id(0)

    def test_random_id_is_16(self):
        assert len(str(random_id())) == 16

    def test_ids_differ(self):
        ids = {generate_id(16) for _ in range(20)}
        assert len(ids) == 20


# ---------- لینک ----------

class TestLinks:
    def test_join_from_url(self):
        assert extract_join_token("https://ble.ir/join/AbC123") == "AbC123"

    def test_join_without_scheme(self):
        assert extract_join_token("ble.ir/join/XyZ") == "XyZ"

    def test_join_bare_token(self):
        assert extract_join_token("AbC123") == "AbC123"

    def test_join_with_dash(self):
        assert extract_join_token("https://ble.ir/join/a-b_c") == "a-b_c"

    def test_join_none(self):
        assert extract_join_token("سلام") is None
        assert extract_join_token("") is None

    def test_username_at(self):
        assert extract_username("@daniyal") == "daniyal"

    def test_username_url(self):
        assert extract_username("https://ble.ir/daniyal") == "daniyal"

    def test_username_trailing_slash(self):
        assert extract_username("https://ble.ir/daniyal/") == "daniyal"

    def test_username_invalid(self):
        assert extract_username("a") is None


# ---------- int64 ----------

class TestInt64:
    def test_roundtrip(self):
        values = [0, 1, 127, 128, 300, 70000, 2**40]
        assert decode_int64_list(encode_int64_list(values)) == values

    def test_empty(self):
        assert decode_int64_list(b"") == []

    def test_hex_input(self):
        encoded = encode_int64_list([1, 300])
        assert decode_int64_list(encoded.hex()) == [1, 300]

    def test_known_encoding(self):
        # 300 = 0xAC 0x02 در varint
        assert encode_int64_list([300]) == b"\xac\x02"

    def test_truncated_raises(self):
        with pytest.raises(ValueError):
            decode_int64_list(b"\x80")


# ---------- نمایش ----------

class TestFormat:
    def test_bytes(self):
        assert format_bytes(500) == "500 B"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(1536000) == "1.5 MB"
        assert format_bytes(2 * 1024**3) == "2.00 GB"

    def test_progress_bar_runs(self, capsys):
        cb = create_progress_bar("تست")
        cb(50, 100)
        cb(100, 100)
        out = capsys.readouterr().out
        assert "تست" in out
        assert "100.0%" in out

    def test_progress_unknown_total(self, capsys):
        cb = create_progress_bar("تست")
        cb(1234)
        assert "B" in capsys.readouterr().out


# ---------- فارسی ----------

class TestPersian:
    def test_to_persian(self):
        assert to_persian_digits(1234) == "۱۲۳۴"
        assert to_persian_digits("a1b2") == "a۱b۲"

    def test_to_english(self):
        assert to_english_digits("۱۲۳۴") == "1234"
        assert to_english_digits("٤٥٦") == "456"

    def test_normalize_phone_persian(self):
        assert normalize_phone("۰۹۱۲۳۴۵۶۷۸۹") == "989123456789"

    def test_normalize_phone_plus(self):
        assert normalize_phone("+98 912 345 6789") == "989123456789"

    def test_normalize_phone_leading_zero(self):
        assert normalize_phone("09123456789") == "989123456789"

    def test_normalize_phone_already_ok(self):
        assert normalize_phone("989123456789") == "989123456789"

    def test_normalize_phone_00_prefix(self):
        assert normalize_phone("00989123456789") == "989123456789"


# ---------- throttle ----------

class TestThrottle:
    def test_runs_callable(self):
        import asyncio

        async def double(x):
            return x * 2

        t = Throttle(rate=0.0)
        assert asyncio.get_event_loop().run_until_complete(t.run(double, 5)) == 10

    def test_retries_then_succeeds(self):
        import asyncio

        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("موقت")
            return "ok"

        t = Throttle(rate=0.0, max_retries=3)
        assert asyncio.get_event_loop().run_until_complete(t.run(flaky)) == "ok"
        assert calls["n"] == 2

    def test_raises_after_max(self):
        import asyncio

        async def always_fail():
            raise RuntimeError("همیشه")

        t = Throttle(rate=0.0, max_retries=2)
        with pytest.raises(RuntimeError):
            asyncio.get_event_loop().run_until_complete(t.run(always_fail))


# ---------- keyboard builder ----------

class TestInlineBuilder:
    def test_single_button(self):
        m = InlineKeyboardBuilder().button("الف", callback_data="a").as_markup()
        assert len(m.inline_keyboard) == 1
        assert m.inline_keyboard[0][0].text == "الف"

    def test_adjust_two(self):
        m = (
            InlineKeyboardBuilder()
            .button("۱", callback_data="1")
            .button("۲", callback_data="2")
            .button("۳", callback_data="3")
            .adjust(2)
            .as_markup()
        )
        assert [len(r) for r in m.inline_keyboard] == [2, 1]

    def test_adjust_pattern(self):
        b = InlineKeyboardBuilder()
        for i in range(5):
            b.button(str(i), callback_data=str(i))
        rows = b.export(1, 2)
        # الگوی ۱،۲ می‌چرخد: ۱ + ۲ + ۱ + ۱ = ۵ دکمه
        assert [len(r) for r in rows] == [1, 2, 1, 1]

    def test_url_button(self):
        m = InlineKeyboardBuilder().button("سایت", url="https://x.ir").as_markup()
        assert m.inline_keyboard[0][0].url == "https://x.ir"

    def test_copy_text_button(self):
        m = InlineKeyboardBuilder().button("کپی", copy_text="CODE").as_markup()
        assert m.inline_keyboard[0][0].copy_text.text == "CODE"

    def test_web_app_button(self):
        m = InlineKeyboardBuilder().button("اپ", web_app="https://app.ir").as_markup()
        assert m.inline_keyboard[0][0].web_app.url == "https://app.ir"

    def test_as_dict(self):
        d = InlineKeyboardBuilder().button("الف", callback_data="a").as_dict()
        assert d["inline_keyboard"][0][0]["text"] == "الف"

    def test_attach(self):
        a = InlineKeyboardBuilder().button("۱", callback_data="1")
        b = InlineKeyboardBuilder().button("۲", callback_data="2")
        m = a.attach(b).adjust(2).as_markup()
        assert len(m.inline_keyboard[0]) == 2

    def test_add_ready_button(self):
        from badking.types.keyboard import InlineKeyboardButton

        m = (
            InlineKeyboardBuilder()
            .add(InlineKeyboardButton(text="آماده", callback_data="x"))
            .as_markup()
        )
        assert m.inline_keyboard[0][0].text == "آماده"


class TestReplyBuilder:
    def test_single(self):
        m = ReplyKeyboardBuilder().button("الف").as_markup()
        assert m.keyboard[0][0].text == "الف"

    def test_adjust(self):
        m = (
            ReplyKeyboardBuilder()
            .button("۱")
            .button("۲")
            .button("۳")
            .adjust(2)
            .as_markup()
        )
        assert [len(r) for r in m.keyboard] == [2, 1]

    def test_resize_default(self):
        assert ReplyKeyboardBuilder().button("x").as_markup().resize_keyboard is True

    def test_contact_button(self):
        m = ReplyKeyboardBuilder().button("شماره", request_contact=True).as_markup()
        assert m.keyboard[0][0].request_contact is True


class TestPaginatorParse:
    def test_parse_page(self):
        p = KeyboardPaginator(["a", "b", "c"], per_page=2)
        assert p.parse("page:page:1") == ("page", 1)

    def test_parse_item(self):
        p = KeyboardPaginator(["a"], per_page=2)
        assert p.parse("page:item:0") == ("item", 0)

    def test_parse_noop(self):
        p = KeyboardPaginator(["a"], per_page=2)
        assert p.parse("page:noop") is None

    def test_parse_wrong_prefix(self):
        p = KeyboardPaginator(["a"], per_page=2)
        assert p.parse("other:page:1") is None

    def test_parse_garbage(self):
        p = KeyboardPaginator(["a"], per_page=2)
        assert p.parse("page:page:x") is None

    def test_markup_navigation(self):
        p = KeyboardPaginator(["a", "b", "c", "d"], per_page=2)
        m = p.markup(0)
        nav = m.inline_keyboard[-1]
        texts = [b.text for b in nav]
        assert any("بعدی" in t for t in texts)
        assert not any("قبلی" in t for t in texts)


# ---------- CallbackData ----------

class ProductCB(CallbackData, prefix="product"):
    action: str
    product_id: int


class OrderCB(CallbackData, prefix="order", sep="|"):
    status: str
    count: int
    note: str


class TestCallbackData:
    def test_pack(self):
        assert ProductCB(action="view", product_id=10).pack() == "product:view:10"

    def test_unpack(self):
        cb = ProductCB.unpack("product:view:10")
        assert cb.action == "view"
        assert cb.product_id == 10
        assert isinstance(cb.product_id, int)

    def test_roundtrip(self):
        original = ProductCB(action="buy", product_id=42)
        assert ProductCB.unpack(original.pack()) == original

    def test_custom_separator(self):
        cb = OrderCB(status="paid", count=3, note="ok")
        assert cb.pack() == "order|paid|3|ok"
        assert OrderCB.unpack(cb.pack()).count == 3

    def test_wrong_prefix_raises(self):
        with pytest.raises(ValueError):
            ProductCB.unpack("other:view:10")

    def test_wrong_field_count_raises(self):
        with pytest.raises(ValueError):
            ProductCB.unpack("product:view")

    def test_missing_field_raises(self):
        with pytest.raises(TypeError):
            ProductCB(action="view")

    def test_unknown_field_raises(self):
        with pytest.raises(TypeError):
            ProductCB(action="view", product_id=1, extra=2)

    def test_repr(self):
        assert "ProductCB" in repr(ProductCB(action="view", product_id=1))

    def test_hashable(self):
        a = ProductCB(action="view", product_id=1)
        b = ProductCB(action="view", product_id=1)
        assert {a, b} == {a}

    def test_filter_hit(self):
        f = ProductCB.filter(action="view")
        event = type("E", (), {"data": "product:view:10"})()
        result = f(event)
        assert isinstance(result, dict)
        assert result["callback_data"].product_id == 10

    def test_filter_miss_on_value(self):
        f = ProductCB.filter(action="buy")
        event = type("E", (), {"data": "product:view:10"})()
        assert f(event) is False

    def test_filter_miss_on_prefix(self):
        f = ProductCB.filter()
        event = type("E", (), {"data": "other:view:10"})()
        assert f(event) is False

    def test_filter_no_data(self):
        f = ProductCB.filter()
        assert f(type("E", (), {})()) is False

    def test_filter_callback_data_attr(self):
        f = ProductCB.filter(action="view")
        event = type("E", (), {"callback_data": "product:view:7"})()
        assert f(event)["callback_data"].product_id == 7

    def test_filter_repr(self):
        assert "CallbackFilter" in repr(ProductCB.filter())
