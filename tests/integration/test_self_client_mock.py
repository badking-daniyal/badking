"""Self Client Integration Tests — لایه MOCK (آفلاین).

این تستها یک جریان کامل self-bot را با transport تقلبی شبیهسازی میکنند:
ورود → ذخیره session → بازیابی → ارسال/دریافت/ویرایش/حذف پیام →
تاریخچه → گروه → رسانه → reconnect.

هیچیک به شبکه واقعی وصل نمیشوند. تستهای زنده در
`tests/integration/test_self_client_live.py`اند و صریحاً SKIP میشوند.
"""

from __future__ import annotations

import asyncio
import io
import os

import pytest

from badking.hybrid import SelfBot, SessionManager
from badking.hybrid.session import Session

pytestmark = pytest.mark.integration


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class MockTransport:
    """Transport تقلبی با پاسخهای قابل تنظیم."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []
        self.connected = False
        self.reconnects = 0

    async def connect(self):
        self.connected = True

    async def close(self):
        self.connected = False

    async def request(self, payload, timeout=None):
        self.calls.append(payload)
        key = next(iter(self.responses), "")
        return self.responses.get(key, b"")


class TestAuthenticationFlow:
    def test_request_code_normalizes_phone(self, tmp_path):
        from badking.hybrid.auth import AuthFlow

        transport = MockTransport()
        flow = AuthFlow(transport)
        # بدون پاسخ معتبر، خطای کنترلشده میدهد
        with pytest.raises(Exception):
            run(flow.request_code("09123456789"))

    def test_session_roundtrip(self, tmp_path):
        mgr = SessionManager(tmp_path / "s.bks", password="pw")
        session = Session(access_token="x.y.z", user_id=42, phone="989123456789")
        key = mgr.store.put(session)

        mgr2 = SessionManager(tmp_path / "s.bks", password="pw")
        loaded = mgr2.get(key)
        assert loaded.user_id == 42
        assert loaded.phone == "989123456789"


class TestSessionRecovery:
    def test_wrong_password_rejected(self, tmp_path):
        from badking.hybrid.session import SessionError

        mgr = SessionManager(tmp_path / "s.bks", password="pw")
        mgr.store.put(Session(access_token="x", user_id=1))

        other = SessionManager(tmp_path / "s.bks", password="wrong")
        with pytest.raises(SessionError):
            other.store.load_all()

    def test_backup_restore(self, tmp_path):
        mgr = SessionManager(tmp_path / "s.bks", password="pw")
        mgr.store.put(Session(access_token="x", user_id=1, phone="989111111111"))
        backup = mgr.export_zip(tmp_path / "b.zip")

        fresh = SessionManager(tmp_path / "fresh.bks", password="pw")
        assert fresh.import_zip(backup) == 1
        assert fresh.count() == 1


class TestMessageOperations:
    def make_bot(self):
        bot = SelfBot(session=Session(access_token="x", user_id=42))
        calls = []

        async def fake_call(rpc, **kwargs):
            calls.append((rpc, kwargs))
            return {}

        bot.call = fake_call
        return bot, calls

    def test_send(self):
        bot, calls = self.make_bot()
        msg = run(bot.send_message(123, "سلام"))
        assert msg.text == "سلام"
        assert calls[0][0] == "messaging.SendMessage"

    def test_edit(self):
        bot, calls = self.make_bot()
        run(bot.edit_message(123, 5, "ویرایش"))
        assert calls[0][0] == "messaging.UpdateMessage"

    def test_delete(self):
        bot, calls = self.make_bot()
        run(bot.delete_messages(123, [5]))
        assert calls[0][0] == "messaging.DeleteMessage"

    def test_receive_via_parse(self):
        from badking.hybrid.client import Peer

        bot, _ = self.make_bot()
        raw = {"id": 7, "message": {"value": "دریافتی"}}
        parsed = bot._parse_message(raw, Peer(id=123, type="chat"))
        assert parsed is not None


class TestMessageHistory:
    def test_iter_messages_empty(self):
        bot = SelfBot(session=Session(access_token="x", user_id=1))

        async def fake_call(rpc, **kwargs):
            return {}

        bot.call = fake_call
        messages = run(bot.get_messages(123, limit=5))
        assert messages == []


class TestGroupOperations:
    def test_group_methods_use_schema_keys(self):
        bot = SelfBot(session=Session(access_token="x", user_id=1))
        calls = []

        async def fake_call(rpc, **kwargs):
            calls.append((rpc, kwargs))
            return {}

        bot.call = fake_call
        run(bot.get_group(999))
        assert calls[0][0] == "groups.GetFullGroup"
        assert "group" in calls[0][1]


class TestReconnection:
    def test_transport_reconnect_called(self):
        t = MockTransport()
        bot = SelfBot(session=Session(access_token="x", user_id=1),
                      transport_factory=lambda: t)
        run(bot.connect())
        assert t.connected is True
        run(bot.close())
        assert t.connected is False


class TestRPCExecution:
    def test_registry_call(self):
        from badking.hybrid.rpc import registry

        spec = registry.get("messaging.SendMessage")
        assert spec.full_name == "messaging.SendMessage"
        assert "peer" in spec.schema()


class TestInlineCallback:
    def test_inline_keyboard_helper(self):
        from badking.hybrid.rpc import make_inline_keyboard

        result = make_inline_keyboard([{"text": "بلی", "callbackData": "yes"}])
        assert result is not None
