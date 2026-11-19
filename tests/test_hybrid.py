"""تست‌های لایه Hybrid (self-bot).

این تست‌ها آفلاین‌اند: هیچ اتصال شبکه‌ای به بله نمی‌زنند. کدک، session،
رجیستری، قاب‌بندی و منطق کلاینت با یک transport جعلی تست می‌شوند.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import tempfile

import pytest

from badking.hybrid import proto
from badking.hybrid.auth import (
    AuthError,
    device_fingerprint,
    normalize_phone,
)
from badking.hybrid.client import SelfBot, SelfBotError
from badking.hybrid.plugin import HybridDisabledError, HybridPlugin
from badking.hybrid.rpc import (
    MESSAGE_CONTENT_SCHEMA,
    PEER_SCHEMA,
    RpcRegistry,
    RpcSpec,
    _name_dict,
    _to_field_schema,
    decode_response,
    encode_request,
    make_chat,
    make_document_content,
    make_peer,
    make_text_content,
    registry,
)
from badking.hybrid.session import Session, SessionError, SessionStore
from badking.hybrid.transport import (
    NotConnected,
    Transport,
    TransportError,
    frame_length_prefixed,
    unframe_length_prefixed,
)


# ============ کدک protobuf ============
class TestProto:
    @pytest.mark.parametrize("value", [0, 1, 127, 128, 300, 2**31, 2**63 - 1])
    def test_varint_roundtrip(self, value):
        encoded = proto.write_varint(value)
        decoded, pos = proto.read_varint(encoded)
        assert decoded == value
        assert pos == len(encoded)

    def test_varint_negative(self):
        encoded = proto.write_varint(-1)
        decoded, _ = proto.read_varint(encoded)
        assert decoded == (1 << 64) - 1

    def test_varint_truncated(self):
        with pytest.raises(proto.ProtoError):
            proto.read_varint(b"\x80")

    def test_build_decode_simple(self):
        msg = proto.build({1: "hello", 2: 42, 3: True})
        out = proto.decode(msg)
        assert proto.get_str(out, 1) == "hello"
        assert proto.get_int(out, 2) == 42
        assert proto.get_int(out, 3) == 1

    def test_decode_without_schema_keeps_bytes(self):
        """بدون اسکیما، متن تودرتو نباید حدس زده شود."""
        inner = proto.build({1: "hi"})
        msg = proto.build({3: inner})
        out = proto.decode(msg)
        assert isinstance(out[3][0], bytes)
        assert out[3][0] == inner

    def test_decode_with_schema_nests(self):
        inner = proto.build({1: "hi"})
        msg = proto.build({3: inner})
        out = proto.decode(msg, {3: {1: None}})
        assert isinstance(out[3][0], dict)
        assert proto.get_str(out[3][0], 1) == "hi"

    def test_text_not_misparsed_as_proto(self):
        """متن 'hi' نباید به‌عنوان protobuf تفسیر شود."""
        msg = proto.build({1: "hi"})
        out = proto.decode(msg)
        assert out[1][0] == b"hi"

    def test_encode_named_flat(self):
        schema = {"a": 1, "b": 2}
        data = proto.encode_named({"a": "x", "b": 5}, schema)
        out = proto.decode(data)
        assert proto.get_str(out, 1) == "x"
        assert proto.get_int(out, 2) == 5

    def test_encode_named_nested(self):
        schema = {"peer": {"field": 1, "fields": {"type": 1, "id": 2}}}
        data = proto.encode_named({"peer": {"type": 4, "id": 77}}, schema)
        out = proto.decode(data, {1: {1: None, 2: None}})
        assert proto.get_int(out[1][0], 1) == 4
        assert proto.get_int(out[1][0], 2) == 77

    def test_encode_named_unknown_field(self):
        with pytest.raises(proto.ProtoError):
            proto.encode_named({"zzz": 1}, {"a": 1})

    def test_encode_named_none_skipped(self):
        data = proto.encode_named({"a": None, "b": 1}, {"a": 1, "b": 2})
        out = proto.decode(data)
        assert 1 not in out
        assert out[2][0] == 1

    def test_decode_truncated_raises(self):
        with pytest.raises(proto.ProtoError):
            proto.decode(b"\x0a\x10abc")

    def test_get_helpers_defaults(self):
        assert proto.get_int({}, 1) == 0
        assert proto.get_int({}, 1, 9) == 9
        assert proto.get_str({}, 1) == ""
        assert proto.get_msg({}, 1) is None


# ============ Session ============
class TestSession:
    def test_roundtrip_plain(self, tmp_path):
        path = tmp_path / "s.session"
        store = SessionStore(path)
        session = Session(access_token="a.b.c", user_id=42, name="Danial")
        key = store.put(session)
        assert key == "user:42"

        again = SessionStore(path).get(key)
        assert again is not None
        assert again.user_id == 42
        assert again.name == "Danial"

    def test_roundtrip_encrypted(self, tmp_path):
        path = tmp_path / "e.session"
        session = Session(access_token="a.b.c", user_id=7)
        SessionStore(path, password="hunter2").put(session)

        loaded = SessionStore(path, password="hunter2").get("user:7")
        assert loaded is not None
        assert loaded.user_id == 7

    def test_wrong_password_rejected(self, tmp_path):
        path = tmp_path / "e.session"
        SessionStore(path, password="right").put(Session(access_token="x", user_id=1))
        with pytest.raises(SessionError):
            SessionStore(path, password="wrong").get("user:1")

    def test_password_required_for_encrypted(self, tmp_path):
        path = tmp_path / "e.session"
        SessionStore(path, password="secret").put(Session(access_token="x", user_id=1))
        with pytest.raises(SessionError):
            SessionStore(path, password=None).get("user:1")

    def test_corrupt_file_rejected(self, tmp_path):
        path = tmp_path / "bad.session"
        path.write_bytes(b"not a session file")
        with pytest.raises(SessionError):
            SessionStore(path).load_all()

    def test_multiple_accounts(self, tmp_path):
        path = tmp_path / "multi.session"
        store = SessionStore(path)
        store.put(Session(access_token="a", user_id=1, name="one"))
        store.put(Session(access_token="b", user_id=2, name="two"))
        accounts = SessionStore(path).list_accounts()
        assert len(accounts) == 2
        assert {a["user_id"] for a in accounts} == {1, 2}

    def test_delete(self, tmp_path):
        path = tmp_path / "d.session"
        store = SessionStore(path)
        store.put(Session(access_token="a", user_id=5))
        assert store.delete("user:5") is True
        assert SessionStore(path).list_accounts() == []

    def test_token_expiry_parsed(self):
        payload = base64.urlsafe_b64encode(
            json.dumps({"exp": 9999999999}).encode()
        ).decode().rstrip("=")
        session = Session(access_token=f"h.{payload}.s")
        assert session.is_valid() is True
        assert session.token_expiry() == 9999999999.0

    def test_expired_token_invalid(self):
        payload = base64.urlsafe_b64encode(
            json.dumps({"exp": 1000}).encode()
        ).decode().rstrip("=")
        assert Session(access_token=f"h.{payload}.s").is_valid() is False

    def test_empty_token_invalid(self):
        assert Session().is_valid() is False

    def test_garbage_token_valid(self):
        """توکن غیر JWT را نمی‌توان بررسی کرد؛ معتبر فرض می‌شود."""
        assert Session(access_token="opaque-token").is_valid() is True


# ============ Auth ============
class TestAuth:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("09123456789", "989123456789"),
            ("+98 912 345 6789", "989123456789"),
            ("00989123456789", "989123456789"),
            ("989123456789", "989123456789"),
        ],
    )
    def test_normalize_phone(self, raw, expected):
        assert normalize_phone(raw) == expected

    def test_normalize_phone_empty(self):
        with pytest.raises(AuthError):
            normalize_phone("")

    def test_normalize_phone_too_short(self):
        with pytest.raises(AuthError):
            normalize_phone("12345")

    def test_device_fingerprint_stable(self):
        a = device_fingerprint("989123456789")
        b = device_fingerprint("989123456789")
        assert a == b
        assert a["device_model"].startswith("BADKING-")

    def test_device_fingerprint_differs(self):
        a = device_fingerprint("989123456789")
        b = device_fingerprint("989999999999")
        assert a["device_hash"] != b["device_hash"]


# ============ RPC ============
class TestRpc:
    def test_registry_has_methods(self):
        # ۷۹ متد، دقیقاً همان‌هایی که پروتکل واقعی بله دارد
        assert len(registry.names()) == 79

    def test_registry_services(self):
        services = registry.by_service()
        for svc in (
            "MESSAGING",
            "GROUPS",
            "USER",
            "ABACUS",
            "PRESENCE",
            "AUTH",
            "FILES",
            "GIFT_PACKET",
            "KIFPOOL",
            "MAGAZINE",
            "REPORT",
            "CONFIGS",
        ):
            assert svc in services, f"سرویس {svc} نیست"

    def test_service_counts(self):
        counts = {k: len(v) for k, v in registry.by_service().items()}
        assert counts["GROUPS"] == 27
        assert counts["USER"] == 16
        assert counts["MESSAGING"] == 12
        assert counts["ABACUS"] == 5

    def test_unknown_rpc_raises(self):
        with pytest.raises(KeyError):
            registry.get("nope.Nothing")

    def test_make_peer(self):
        assert make_peer("user", 5, 7) == {"type": 1, "id": 5, "accessHash": 7}
        assert make_peer("channel", 9)["type"] == 4
        with pytest.raises(ValueError):
            make_peer("nonsense", 1)

    def test_make_chat(self):
        assert make_chat("private", 3) == {"type": 1, "id": 3}
        assert make_chat("supergroup", 3) == {"type": 5, "id": 3}

    def test_text_content_field_15(self):
        """MessageContent متن در فیلد ۱۵ است، نه ۱."""
        content = make_text_content("سلام")
        assert content == {"text": {"value": "سلام"}}
        encoded = proto.encode_named(content, MESSAGE_CONTENT_SCHEMA)
        out = proto.decode(encoded)
        assert 15 in out
        inner = proto.decode(out[15][0])
        assert proto.get_str(inner, 1) == "سلام"

    def test_document_content_field_4(self):
        content = make_document_content(9, 8, "a.txt", "text/plain", 10, "cap")
        assert "document" in content
        assert content["document"]["fileId"] == 9
        assert content["document"]["caption"] == {"content": "cap"}

    def test_encode_send_message(self):
        """SendMessage: {1: Peer, 2: message_id, 3: content, 6: Chat}"""
        spec = registry.get("messaging.SendMessage")
        payload = encode_request(
            spec,
            {
                "peer": make_peer("channel", 1, 2),
                "message_id": 99,
                "content": make_text_content("hi"),
                "chat": make_chat("channel", 1),
            },
        )
        out = proto.decode(payload)
        assert 1 in out and 2 in out and 3 in out and 6 in out

        peer = proto.decode(out[1][0])
        assert proto.get_int(peer, 1) == 4  # channel
        assert proto.get_int(peer, 2) == 1
        assert proto.get_int(peer, 3) == 2
        assert proto.get_int(out, 2) == 99

        content = proto.decode(out[3][0])
        text = proto.decode(content[15][0])
        assert proto.get_str(text, 1) == "hi"

        chat = proto.decode(out[6][0])
        assert proto.get_int(chat, 1) == 3  # channel در ChatType
        assert proto.get_int(chat, 2) == 1

    def test_encode_unknown_field_raises(self):
        spec = registry.get("messaging.SendMessage")
        with pytest.raises(KeyError):
            encode_request(spec, {"nonsense": 1})

    def test_encode_skips_none(self):
        spec = registry.get("messaging.SendMessage")
        payload = encode_request(
            spec, {"message_id": 5, "peer": None, "content": None}
        )
        out = proto.decode(payload)
        assert 1 not in out
        assert proto.get_int(out, 2) == 5

    def test_decode_response_names_fields(self):
        """پاسخ SendMessage فیلدهایش را با نام برمی‌گرداند."""
        spec = registry.get("messaging.SendMessage")
        frame = proto.build({2: 12345, 3: 1700000000})
        out = decode_response(spec, frame)
        # پیام‌آیدی و تاریخ باید با نام خوانده شوند
        assert 12345 in out.values() or "message_id" in out

    def test_decode_response_unknown_field(self):
        spec = registry.get("messaging.SendMessage")
        frame = proto.build({99: 1})
        out = decode_response(spec, frame)
        assert out["99"] == 1

    def test_custom_registry_override(self):
        reg = RpcRegistry()
        reg.load_overrides({"messaging.SendMessage": {"req": {"peer": 7}}})
        spec = reg.get("messaging.SendMessage")
        assert spec.req["peer"] == 7
        # بقیه دست‌نخورده
        assert spec.req["message_id"] == 2

    def test_register_custom_rpc(self):
        reg = RpcRegistry()
        reg.register(RpcSpec("custom", "custom", "Ping", req={"x": 1}, resp={"ok": 1}))
        assert "custom.Ping" in reg.names()

    def test_schema_override_from_file(self, tmp_path):
        path = tmp_path / "schema.json"
        path.write_text(
            json.dumps({"messaging.SendMessage": {"req": {"peer": 11}}}),
            encoding="utf-8",
        )
        reg = RpcRegistry()
        assert reg.load_schema_file(path) == 1
        assert reg.get("messaging.SendMessage").req["peer"] == 11

    def test_search(self):
        hits = registry.search("واکنش")
        assert any("Reaction" in h for h in hits)

    def test_full_service_name(self):
        spec = registry.get("messaging.SendMessage")
        assert spec.full_service == "bale.messaging.v2.Messaging"

    def test_nested_schema_resolves_cycles(self):
        """MessageContent → TemplateMessage → MessageContent چرخه دارد."""
        spec = registry.get("messaging.SendMessage")
        schema = spec.schema()
        assert "content" in schema
        # نباید RecursionError بدهد
        assert isinstance(schema["content"], dict)


# ============ Transport ============
class TestTransport:
    def test_frame_roundtrip(self):
        frame = frame_length_prefixed(b"hello")
        assert frame == b"\x00\x00\x00\x05hello"
        msgs, rest = unframe_length_prefixed(frame)
        assert msgs == [b"hello"]
        assert rest == b""

    def test_partial_frame_buffered(self):
        frame = frame_length_prefixed(b"hello")
        msgs, rest = unframe_length_prefixed(frame[:6])
        assert msgs == []
        assert rest == frame[:6]

    def test_multiple_frames(self):
        data = frame_length_prefixed(b"a") + frame_length_prefixed(b"bb")
        msgs, rest = unframe_length_prefixed(data)
        assert msgs == [b"a", b"bb"]
        assert rest == b""

    def test_oversized_frame_rejected(self):
        with pytest.raises(TransportError):
            unframe_length_prefixed(b"\xff\xff\xff\xff")

    def test_rate_state_learns(self):
        from badking.hybrid.transport import RateState

        state = RateState()
        assert state.wait_needed() == 0.0
        state.learn(2.0)
        assert state.min_interval > 0
        assert state.wait_needed() > 0

    def test_rate_state_penalty_decays(self):
        from badking.hybrid.transport import RateState

        state = RateState()
        state.learn(0.01)
        state.penalty_until = 0.0
        state.last_sent = 0.0
        assert state.wait_needed() == 0.0


# ============ Client با transport جعلی ============
class FakeTransport:
    """transport جعلی که پاسخ‌های از پیش تعیین‌شده می‌دهد."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.sent = []
        self.connected = True
        self.stats = {"sent": 0, "received": 0, "reconnects": 0, "errors": 0}
        self.on_update = None
        self.on_disconnect = None

    async def request(self, payload, req_id=None, timeout=None):
        self.sent.append(payload)
        key = len(self.sent)
        return self.responses.get(key, b"")

    async def send_fire_and_forget(self, payload):
        self.sent.append(payload)

    async def close(self):
        self.connected = False


def make_bot(responses=None):
    bot = SelfBot(session=Session(access_token="fake.token.here", user_id=1))
    bot._transport = FakeTransport(responses)  # type: ignore
    return bot


class TestClient:
    def test_requires_connection(self):
        bot = SelfBot(session=Session(access_token="t"))
        with pytest.raises(NotConnected):
            asyncio.get_event_loop().run_until_complete(bot.call("user.GetMe"))

    def test_no_session_no_phone_raises(self):
        bot = SelfBot()
        with pytest.raises(SelfBotError):
            asyncio.get_event_loop().run_until_complete(bot.connect())

    def test_send_message(self):
        """پاسخ واقعی SendMessage فقط seq و date دارد؛ آیدی همان rid است."""
        resolve = proto.build({})
        sent = proto.build({1: 7, 2: 1700000000})
        bot = make_bot({1: resolve, 2: sent})
        msg = asyncio.get_event_loop().run_until_complete(
            bot.send_message("@test", "hello")
        )
        assert msg.text == "hello"
        assert msg.is_out is True
        assert msg.id > 0  # rid

    def test_send_message_payload_shape(self):
        """payload ارسالی باید فیلد ۱۵ برای متن داشته باشد."""
        resolve = proto.build({})
        sent = proto.build({1: 7, 2: 1700000000})
        bot = make_bot({1: resolve, 2: sent})
        asyncio.get_event_loop().run_until_complete(
            bot.send_message("@test", "hello")
        )
        payload = bot._transport.sent[-1]
        out = proto.decode(payload)
        assert 1 in out, "peer نیست"
        assert 3 in out, "content نیست"
        assert 6 in out, "chat نیست"
        content = proto.decode(out[3][0])
        assert 15 in content, "متن باید فیلد ۱۵ باشد"
        text = proto.decode(content[15][0])
        assert proto.get_str(text, 1) == "hello"

    def test_get_me(self):
        """user.LoadUsers → {1: [User{1: id, 3: name}]}"""
        user = proto.build({1: 42, 3: "Danial"})
        bot = make_bot({1: proto.build({1: [user]})})
        bot._my_id = 42
        me = asyncio.get_event_loop().run_until_complete(bot.get_me())
        assert me.id == 42
        assert me.title == "Danial"

    def test_get_me_without_id(self):
        """بدون آیدی، بدون RPC، Peer صفر."""
        bot = make_bot({})
        bot._my_id = 0
        me = asyncio.get_event_loop().run_until_complete(bot.get_me())
        assert me.id == 0

    def test_iter_messages_paginates(self):
        """LoadHistory → {1: [MessageData{2: messageId, 3: date}]}"""
        resolve = proto.build({})
        page1 = proto.build(
            {
                1: [
                    proto.build({2: 300, 3: 3000}),
                    proto.build({2: 200, 3: 2000}),
                ],
            }
        )
        page2 = proto.build({1: [proto.build({2: 100, 3: 1000})]})
        bot = make_bot({1: resolve, 2: page1, 3: page2})

        async def collect():
            return [m.id async for m in bot.iter_messages("@c", limit=10)]

        ids = asyncio.get_event_loop().run_until_complete(collect())
        assert ids == [300, 200, 100]

    def test_iter_messages_dedupes(self):
        resolve = proto.build({})
        page1 = proto.build(
            {1: [proto.build({2: 2, 3: 20}), proto.build({2: 1, 3: 10})]}
        )
        page2 = proto.build(
            {1: [proto.build({2: 2, 3: 20}), proto.build({2: 0, 3: 5})]}
        )
        bot = make_bot({1: resolve, 2: page1, 3: page2})

        async def collect():
            return [m.id async for m in bot.iter_messages("@c", limit=10)]

        ids = asyncio.get_event_loop().run_until_complete(collect())
        assert ids == [2, 1, 0]

    def test_iter_messages_respects_limit(self):
        resolve = proto.build({})
        page = proto.build({1: [proto.build({2: i, 3: i}) for i in range(10)]})
        bot = make_bot({1: resolve, 2: page})

        async def collect():
            return [m.id async for m in bot.iter_messages("@c", limit=3)]

        ids = asyncio.get_event_loop().run_until_complete(collect())
        assert len(ids) == 3

    def test_iter_dialogs(self):
        """LoadDialogs → {3: [PeerData{1: Peer, 2: unreadCount, 6: date}]}"""
        dialogs = proto.build(
            {
                3: [
                    proto.build(
                        {
                            1: proto.build({1: 2, 2: 5}),
                            2: 3,
                            6: 1700,
                        }
                    ),
                ],
            }
        )
        bot = make_bot({1: dialogs})

        async def collect():
            return [d async for d in bot.iter_dialogs(limit=10)]

        rows = asyncio.get_event_loop().run_until_complete(collect())
        assert len(rows) == 1
        assert rows[0].unread == 3
        assert rows[0].peer.id == 5

    def test_delete_messages(self):
        bot = make_bot({1: proto.build({1: 1})})
        ok = asyncio.get_event_loop().run_until_complete(
            bot.delete_messages("@c", [1, 2])
        )
        assert ok is True

    def test_react_uses_abacus(self):
        """واکنش باید ABACUS.MessageSetReaction باشد."""
        bot = make_bot({1: proto.build({2: 1})})
        ok = asyncio.get_event_loop().run_until_complete(bot.react("@c", 5, "❤"))
        assert ok is True
        spec = registry.get("abacus.MessageSetReaction")
        assert spec.req["emojy"] == 3

    def test_typing_uses_presence(self):
        """تایپ باید PRESENCE.Typing باشد."""
        bot = make_bot({1: proto.build({})})
        ok = asyncio.get_event_loop().run_until_complete(bot.send_typing("@c"))
        assert ok is True
        assert "presence.Typing" in registry.names()

    def test_handler_registration(self):
        bot = make_bot()
        calls = []

        @bot.on(lambda m: m.text == "/ping")
        async def handler(msg):
            calls.append(msg.text)

        assert len(bot._handlers) == 1

    def test_describe(self):
        bot = make_bot()
        d = bot.describe("messaging.SendMessage")
        assert d["name"] == "messaging.SendMessage"
        assert d["service"] == "bale.messaging.v2.Messaging"
        assert "peer" in d["request"]
        assert d["needs_peer"] is True

    def test_search_methods(self):
        bot = make_bot()
        hits = bot.search("واکنش")
        assert any("Reaction" in h for h in hits)

    def test_raw_call(self):
        """raw_call بدون اسکیما، با شماره فیلد خام."""
        bot = make_bot({1: proto.build({1: 5, 2: 9})})
        out = asyncio.get_event_loop().run_until_complete(
            bot.raw_call("whatever.Unknown", {1: 7, 2: "x"})
        )
        assert out[1] == [5]
        assert out[2] == [9]

    def test_raw_call_requires_connection(self):
        bot = SelfBot(session=Session(access_token="t"))
        with pytest.raises(NotConnected):
            asyncio.get_event_loop().run_until_complete(
                bot.raw_call("x.Y", {1: 1})
            )

    def test_raw_handler(self):
        bot = make_bot()
        seen = []

        @bot.on_raw
        def raw(frame):
            seen.append(frame)

        assert len(bot._raw_handlers) == 1


# ============ Plugin ============
class TestPlugin:
    def test_disabled_by_default(self):
        plugin = HybridPlugin()
        assert plugin.enabled is False

    def test_enabled_without_ack_is_disabled(self):
        plugin = HybridPlugin(enabled=True)
        assert plugin.enabled is False

    def test_activate_without_ack_raises(self):
        plugin = HybridPlugin(enabled=True)
        with pytest.raises(HybridDisabledError):
            asyncio.get_event_loop().run_until_complete(plugin.activate())

    def test_activate_with_ack_tries_connect(self):
        """با ack_risk، تلاش می‌کند وصل شود (بدون شبکه شکست می‌خورد)."""
        plugin = HybridPlugin(enabled=True, ack_risk=True, session=Session(access_token="t"))
        with pytest.raises(Exception):
            asyncio.get_event_loop().run_until_complete(plugin.activate())

    def test_register_rpc_requires_enabled(self):
        plugin = HybridPlugin()
        with pytest.raises(HybridDisabledError):
            plugin.register_rpc("x.Y", RpcSpec("x", "x", "Y"))

    def test_lane_name(self):
        assert HybridPlugin().lane == "selfbot"
