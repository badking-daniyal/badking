"""Regression tests براساس ممیزی Self Client.

هر تست مربوط به یک باگ واقعی است که در ممیزی پیدا و رفع شد.
این تستها تضمین میکنند دوباره پیش نیایند.
"""

from __future__ import annotations

import asyncio

import pytest

from badking.hybrid import SelfBot
from badking.hybrid.rpc import make_chat
from badking.hybrid.session import Session


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def make_bot(uid: int = 42):
    """SelfBot با session واقعی و call تقلبی."""
    bot = SelfBot(session=Session(access_token="x", user_id=uid, phone="989123456789"))
    calls: list[tuple[str, dict]] = []

    async def fake_call(rpc_name, **kwargs):
        calls.append((rpc_name, kwargs))
        return {}

    bot.call = fake_call  # type: ignore[method-assign]
    return bot, calls


# ---------- F2: _my_id init order ----------

class TestMyId:
    def test_my_id_from_session_object(self):
        bot, _ = make_bot(42)
        assert bot._my_id == 42

    def test_get_me_uses_real_id(self):
        bot, calls = make_bot(42)
        me = run(bot.get_me())
        assert me.id == 42
        assert calls[0][1]["peers"] == [{"id": 42, "type": 1}]

    def test_my_id_zero_without_session(self):
        bot = SelfBot()
        assert bot._my_id == 0


# ---------- F: wallet service ----------

class TestWallet:
    def test_wallet_uses_kifpool(self):
        bot, calls = make_bot()
        run(bot.get_wallet())
        assert calls[0][0] == "kifpool.GetMyKifpools"

    def test_no_duplicate_get_wallet(self):
        import inspect
        from badking.hybrid.client import SelfBot as SB

        # فقط یک تعریف get_wallet وجود دارد
        src = inspect.getsource(SB)
        assert src.count("async def get_wallet") == 1


# ---------- F: make_chat peer types ----------

class TestMakeChat:
    @pytest.mark.parametrize("peer_type", ["user", "chat", "group", "channel", "private"])
    def test_all_peer_types_accepted(self, peer_type):
        result = make_chat(peer_type, 123)
        assert result["id"] == 123
        assert isinstance(result["type"], int)

    def test_send_message_with_numeric_ref(self):
        bot, calls = make_bot()
        msg = run(bot.send_message(999, "سلام"))
        assert msg.chat_id == 999
        assert calls[0][0] == "messaging.SendMessage"


# ---------- F: group methods schema keys ----------

class TestGroupSchemaKeys:
    @pytest.mark.parametrize(
        "method,args,expected_rpc,expected_key",
        [
            ("get_group", (123,), "groups.GetFullGroup", "group"),
            ("leave_group", (123,), "groups.LeaveGroup", "group"),
            ("get_members", (123,), "groups.LoadMembers", "group"),
            ("get_invite_link", (123,), "groups.GetGroupInviteURL", "group"),
        ],
    )
    def test_group_key(self, method, args, expected_rpc, expected_key):
        bot, calls = make_bot()
        coro = getattr(bot, method)(*args)
        run(coro)
        assert calls[-1][0] == expected_rpc
        assert expected_key in calls[-1][1]

    def test_block_user_uses_peer(self):
        bot, calls = make_bot()
        run(bot.block_user(5))
        assert "peer" in calls[-1][1]
        assert "user_id" not in calls[-1][1]

    def test_check_username_uses_nick_name(self):
        bot, calls = make_bot()
        run(bot.check_username("foo"))
        assert "nick_name" in calls[-1][1]
        assert "nickname" not in calls[-1][1]

    def test_edit_about_uses_nested_value(self):
        bot, calls = make_bot()
        run(bot.edit_about("بیو"))
        assert calls[-1][1]["about"] == {"value": "بیو"}

    def test_leave_by_id_uses_short_peer(self):
        bot, calls = make_bot()
        run(bot.leave_by_id(999))
        group = calls[-1][1]["group"]
        assert "id" in group and "accessHash" in group
        assert "type" not in group


# ---------- F: edit_profile dead method ----------

class TestEditProfile:
    def test_edit_profile_uses_real_methods(self):
        bot, calls = make_bot()
        result = run(bot.edit_profile(name="علی", about="سلام"))
        assert result is True
        names = [c[0] for c in calls]
        assert "user.EditName" in names
        assert "user.EditAbout" in names
        assert "users.EditProfile" not in names


# ---------- F: send_message date bytes ----------

class TestSendMessageParsing:
    def test_bytes_date_does_not_crash(self):
        bot, calls = make_bot()
        bot.call = lambda rpc_name, **kw: _call_with_response({"seq": b"\x05", "date": b"\x7f"})
        msg = run(bot.send_message(1, "hi"))
        assert msg.id == 5

    def test_missing_response_uses_local_id(self):
        bot, _ = make_bot()
        msg = run(bot.send_message(1, "hi"))
        assert msg.id > 0


async def _call_with_response(resp):
    return resp


# ---------- F: probe honesty ----------

class TestProbeHonesty:
    def test_probe_known_method(self):
        bot, _ = make_bot()
        result = run(bot.probe("messaging.SendMessage"))
        assert result["exists"] is True
        assert result["server_verified"] is False

    def test_probe_unknown_method(self):
        bot, _ = make_bot()
        result = run(bot.probe("fake.Nope"))
        assert result["exists"] is False
        assert result["server_verified"] is False


# ---------- F: upload failure not silent ----------

class TestUploadFailure:
    def test_missing_url_raises(self, tmp_path):
        from badking.hybrid.client import SelfBotError

        bot, _ = make_bot()
        bot.call = lambda rpc_name, **kw: _call_with_response({})
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(SelfBotError) as info:
            run(bot.send_file(1, str(f)))
        assert "URL" in str(info.value)
