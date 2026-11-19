"""تست Moderation Engine و Channel Monitor."""

from __future__ import annotations

import asyncio
import time

import pytest

from badking.moderation import (
    Action,
    ChannelMonitor,
    ModerationError,
    Moderator,
    Rule,
    flood_rule,
    link_rule,
    mention_spam_rule,
    word_rule,
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------- اشیای تقلبی ----------

class FakeUser:
    def __init__(self, user_id: int, name: str = "کاربر", username: str = "") -> None:
        self.id = user_id
        self.first_name = name
        self.username = username


class FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class FakeMessage:
    def __init__(
        self,
        text: str = "",
        *,
        user_id: int = 1,
        chat_id: int = -100,
        message_id: int = 10,
        document: bool = False,
        photo: bool = False,
    ) -> None:
        self.text = text
        self.caption = ""
        self.from_user = FakeUser(user_id)
        self.chat = FakeChat(chat_id)
        self.message_id = message_id
        self.document = object() if document else None
        self.photo = object() if photo else None


class FakeBot:
    """کلاینت تقلبی که همه اقدام‌ها را ثبت می‌کند."""

    def __init__(self, admins: set[int] | None = None) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.admins = admins or set()

    async def send_message(self, chat_id, text):
        self.calls.append(("send_message", (chat_id, text)))

    async def delete_message(self, chat_id, message_id):
        self.calls.append(("delete_message", (chat_id, message_id)))

    async def ban_chat_member(self, chat_id, user_id):
        self.calls.append(("ban_chat_member", (chat_id, user_id)))

    async def unban_chat_member(self, chat_id, user_id):
        self.calls.append(("unban_chat_member", (chat_id, user_id)))

    async def restrict_chat_member(self, chat_id, user_id, until_date=0):
        self.calls.append(("restrict_chat_member", (chat_id, user_id)))

    async def get_chat_member(self, chat_id, user_id):
        class Member:
            status = "administrator" if user_id in self.admins else "member"

        return Member()


# ---------- Rule ----------

class TestRule:
    def test_requires_a_condition(self):
        with pytest.raises(ModerationError) as info:
            Rule(name="empty")
        assert "هیچ شرطی ندارد" in str(info.value)

    def test_bad_regex(self):
        with pytest.raises(ModerationError) as info:
            Rule(name="bad", pattern="[unclosed")
        assert "خراب" in str(info.value)

    def test_pattern_matches(self):
        rule = Rule(name="links", pattern=r"https?://")
        assert rule.matches("ببین https://x.ir") is True
        assert rule.matches("سلام") is False

    def test_pattern_case_insensitive(self):
        rule = Rule(name="x", pattern="SPAM")
        assert rule.matches("this is spam") is True

    def test_words_match(self):
        rule = Rule(name="w", words=["کسب درآمد"])
        assert rule.matches("راه کسب درآمد سریع") is True
        assert rule.matches("سلام خوبی") is False

    def test_words_case_insensitive(self):
        rule = Rule(name="w", words=["Spam"])
        assert rule.matches("SPAM here") is True

    def test_max_length(self):
        rule = Rule(name="len", max_length=10)
        assert rule.matches("x" * 11) is True
        assert rule.matches("x" * 10) is False

    def test_max_links(self):
        rule = Rule(name="l", max_links=2)
        assert rule.matches("", links=3) is True
        assert rule.matches("", links=2) is False

    def test_max_files(self):
        rule = Rule(name="f", max_files=1)
        assert rule.matches("", files=2) is True

    def test_max_mentions(self):
        rule = Rule(name="m", max_mentions=3)
        assert rule.matches("", mentions=4) is True

    def test_action_from_string(self):
        assert Rule(name="x", words=["a"], action="ban").action == Action.BAN

    def test_bad_action_string(self):
        with pytest.raises(ValueError):
            Rule(name="x", words=["a"], action="nonsense")


# ---------- Moderator ----------

class TestModerator:
    def test_clean_message_passes(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(link_rule())
        found = run(mod.inspect(FakeMessage("سلام خوبی؟")))
        assert found == []
        assert bot.calls == []

    def test_link_triggers_warn(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(link_rule())
        found = run(mod.inspect(FakeMessage("ببین https://spam.ir")))
        assert len(found) == 1
        assert found[0].rule == "links"
        assert any(call[0] == "send_message" for call in bot.calls)

    def test_delete_action(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(Rule(name="d", words=["بد"], action=Action.DELETE))
        run(mod.inspect(FakeMessage("حرف بد")))
        assert ("delete_message", (-100, 10)) in bot.calls

    def test_ban_action(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(Rule(name="b", words=["بد"], action=Action.BAN))
        run(mod.inspect(FakeMessage("حرف بد", user_id=55)))
        assert ("ban_chat_member", (-100, 55)) in bot.calls

    def test_mute_action(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(Rule(name="m", words=["بد"], action=Action.MUTE))
        run(mod.inspect(FakeMessage("حرف بد", user_id=7)))
        assert any(call[0] == "restrict_chat_member" for call in bot.calls)

    def test_kick_bans_then_unbans(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(Rule(name="k", words=["بد"], action=Action.KICK))
        run(mod.inspect(FakeMessage("حرف بد", user_id=9)))
        names = [call[0] for call in bot.calls]
        assert "ban_chat_member" in names
        assert "unban_chat_member" in names

    def test_warn_escalates_to_ban(self):
        bot = FakeBot()
        mod = Moderator(bot, warn_limit=2)
        mod.add_rule(link_rule())

        run(mod.inspect(FakeMessage("https://a.ir", user_id=3)))
        assert mod.warn_count(-100, 3) == 1
        assert not any(c[0] == "ban_chat_member" for c in bot.calls)

        run(mod.inspect(FakeMessage("https://b.ir", user_id=3)))
        assert any(c[0] == "ban_chat_member" for c in bot.calls)
        # بعد از اخراج، شمارنده صفر می‌شود
        assert mod.warn_count(-100, 3) == 0

    def test_warn_limit_zero_never_bans(self):
        bot = FakeBot()
        mod = Moderator(bot, warn_limit=0)
        mod.add_rule(link_rule())
        for _ in range(10):
            run(mod.inspect(FakeMessage("https://a.ir", user_id=3)))
        assert not any(c[0] == "ban_chat_member" for c in bot.calls)

    def test_admin_exempt(self):
        bot = FakeBot(admins={1})
        mod = Moderator(bot)
        mod.add_rule(link_rule())
        found = run(mod.inspect(FakeMessage("https://a.ir", user_id=1)))
        assert found == []

    def test_whitelist(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(link_rule())
        mod.whitelist(5)
        found = run(mod.inspect(FakeMessage("https://a.ir", user_id=5)))
        assert found == []
        assert mod.is_whitelisted(5) is True

    def test_blacklist_bans_immediately(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.blacklist(6)
        found = run(mod.inspect(FakeMessage("سلام", user_id=6)))
        assert len(found) == 1
        assert found[0].rule == "blacklist"
        assert ("ban_chat_member", (-100, 6)) in bot.calls

    def test_whitelist_and_blacklist_exclusive(self):
        mod = Moderator()
        mod.whitelist(1)
        mod.blacklist(1)
        assert mod.is_blacklisted(1) is True
        assert mod.is_whitelisted(1) is False

    def test_unlist(self):
        mod = Moderator()
        mod.blacklist(1)
        mod.unlist(1)
        assert mod.is_blacklisted(1) is False

    def test_multiple_rules_all_fire(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(link_rule())
        mod.add_rule(flood_rule(max_length=10))
        found = run(mod.inspect(FakeMessage("https://a.ir " + "x" * 20)))
        assert len(found) == 2

    def test_remove_rule(self):
        mod = Moderator()
        mod.add_rule(link_rule())
        assert mod.remove_rule("links") is True
        assert mod.remove_rule("links") is False
        assert mod.rule_names() == []

    def test_duplicate_rule_name_replaces(self):
        mod = Moderator()
        mod.add_rule(Rule(name="x", words=["a"]))
        mod.add_rule(Rule(name="x", words=["b"]))
        assert len(mod.rules) == 1

    def test_no_bot_does_not_crash(self):
        mod = Moderator(None)
        mod.add_rule(link_rule())
        found = run(mod.inspect(FakeMessage("https://a.ir")))
        assert len(found) == 1

    def test_client_without_method_skipped(self):
        class Minimal:
            pass

        mod = Moderator(Minimal())
        mod.add_rule(Rule(name="b", words=["x"], action=Action.BAN))
        run(mod.inspect(FakeMessage("x")))
        # نباید خطا بدهد

    def test_violations_recorded(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(link_rule())
        run(mod.inspect(FakeMessage("https://a.ir", user_id=2)))
        assert len(mod.violations()) == 1
        assert len(mod.violations(user_id=2)) == 1
        assert len(mod.violations(user_id=99)) == 0

    def test_reset_warns(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(link_rule())
        run(mod.inspect(FakeMessage("https://a.ir", user_id=3)))
        mod.reset_warns(-100, 3)
        assert mod.warn_count(-100, 3) == 0

    def test_stats(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(link_rule())
        mod.whitelist(1)
        mod.blacklist(2)
        run(mod.inspect(FakeMessage("https://a.ir", user_id=3)))

        stats = mod.stats()
        assert stats["rules"] == 1
        assert stats["violations"] == 1
        assert stats["whitelisted"] == 1
        assert stats["blacklisted"] == 1

    def test_persist_to_storage(self):
        from badking.storage import MemoryStorage

        storage = MemoryStorage()
        bot = FakeBot()
        mod = Moderator(bot, storage=storage)
        mod.add_rule(link_rule())
        run(mod.inspect(FakeMessage("https://a.ir", user_id=4)))

        saved = run(storage.get("mod:-100:4"))
        assert saved is not None
        assert len(saved["history"]) == 1
        assert saved["history"][0]["rule"] == "links"

    def test_photo_counts_as_file(self):
        bot = FakeBot()
        mod = Moderator(bot)
        mod.add_rule(Rule(name="files", max_files=0, action=Action.WARN))
        found = run(mod.inspect(FakeMessage("", photo=True)))
        assert len(found) == 1

    def test_message_without_user_ignored(self):
        mod = Moderator(FakeBot())
        mod.add_rule(link_rule())

        class NoUser:
            text = "https://a.ir"
            chat = FakeChat(-100)
            from_user = None

        assert run(mod.inspect(NoUser())) == []


# ---------- قواعد آماده ----------

class TestPresetRules:
    def test_link_rule(self):
        rule = link_rule()
        assert rule.matches("www.example.com") is True
        assert rule.matches("سلام") is False

    def test_flood_rule(self):
        rule = flood_rule(max_length=5)
        assert rule.matches("x" * 6) is True

    def test_mention_spam_rule(self):
        rule = mention_spam_rule(max_mentions=2)
        assert rule.matches("", mentions=3) is True
        assert rule.action == Action.MUTE

    def test_word_rule(self):
        rule = word_rule(["توهین"])
        assert rule.matches("این توهین است") is True


# ---------- Channel Monitor ----------

class TestChannelMonitor:
    def test_watch_and_list(self):
        m = ChannelMonitor()
        m.watch(-100, admin_id=5, name="کانال من")
        assert m.watched() == [-100]
        assert m.admins_of(-100) == {5}
        assert m.name_of(-100) == "کانال من"

    def test_unwatch(self):
        m = ChannelMonitor()
        m.watch(-100)
        assert m.unwatch(-100) is True
        assert m.unwatch(-100) is False
        assert m.watched() == []

    def test_record_join(self):
        m = ChannelMonitor()
        m.watch(-100)
        event = run(m.record_join(-100, FakeUser(7, "علی", "ali")))
        assert event.kind == "join"
        assert event.user_id == 7
        assert event.name == "علی"

    def test_record_leave(self):
        m = ChannelMonitor()
        m.watch(-100)
        event = run(m.record_leave(-100, FakeUser(8)))
        assert event.kind == "leave"

    def test_stats(self):
        m = ChannelMonitor()
        m.watch(-100)
        loop = asyncio.get_event_loop()
        for i in range(3):
            loop.run_until_complete(m.record_join(-100, FakeUser(i)))
        loop.run_until_complete(m.record_leave(-100, FakeUser(0)))

        stats = m.stats(-100, days=7)
        assert stats.joins == 3
        assert stats.leaves == 1
        assert stats.net == 2
        assert stats.unique_joiners == 3
        assert stats.unique_leavers == 1

    def test_churn(self):
        m = ChannelMonitor()
        m.watch(-100)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(m.record_join(-100, FakeUser(1)))
        loop.run_until_complete(m.record_leave(-100, FakeUser(1)))
        assert m.stats(-100).churn == 1.0

    def test_churn_no_joins(self):
        m = ChannelMonitor()
        m.watch(-100)
        run(m.record_leave(-100, FakeUser(1)))
        assert m.stats(-100).churn == 1.0

    def test_summary_text(self):
        m = ChannelMonitor()
        m.watch(-100)
        run(m.record_join(-100, FakeUser(1)))
        text = m.stats(-100).summary()
        assert "ورود" in text
        assert "خروج" in text

    def test_report(self):
        m = ChannelMonitor()
        m.watch(-100, name="فروشگاه")
        run(m.record_join(-100, FakeUser(1)))
        report = run(m.report(-100))
        assert "فروشگاه" in report

    def test_events_filter_by_kind(self):
        m = ChannelMonitor()
        m.watch(-100)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(m.record_join(-100, FakeUser(1)))
        loop.run_until_complete(m.record_leave(-100, FakeUser(2)))

        assert len(m.events(-100, kind="join")) == 1
        assert len(m.events(-100, kind="leave")) == 1
        assert len(m.events(-100)) == 2

    def test_events_filter_by_days(self):
        m = ChannelMonitor()
        m.watch(-100)
        run(m.record_join(-100, FakeUser(1)))

        # رویداد را به ۱۰ روز قبل ببر
        m._events[-100][0].at = time.time() - 10 * 86400

        assert len(m.events(-100, days=7)) == 0
        assert len(m.events(-100, days=30)) == 1

    def test_max_events_cap(self):
        m = ChannelMonitor(max_events=5)
        m.watch(-100)
        loop = asyncio.get_event_loop()
        for i in range(10):
            loop.run_until_complete(m.record_join(-100, FakeUser(i)))
        assert len(m._events[-100]) == 5

    def test_daily_breakdown(self):
        m = ChannelMonitor()
        m.watch(-100)
        run(m.record_join(-100, FakeUser(1)))
        breakdown = m.daily_breakdown(-100, days=3)
        assert len(breakdown) == 3
        assert sum(d["joins"] for d in breakdown) == 1

    def test_top_growth(self):
        m = ChannelMonitor()
        m.watch(-100, name="الف")
        m.watch(-200, name="ب")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(m.record_join(-100, FakeUser(1)))
        loop.run_until_complete(m.record_join(-100, FakeUser(2)))
        loop.run_until_complete(m.record_join(-200, FakeUser(3)))

        top = m.top_growth()
        assert top[0][0] == -100
        assert top[0][1] == 2

    def test_dashboard(self):
        m = ChannelMonitor()
        m.watch(-100, name="الف")
        run(m.record_join(-100, FakeUser(1)))
        board = m.dashboard()
        assert board["channels"] == 1
        assert board["per_channel"]["الف"]["joins"] == 1

    def test_persist_and_load(self):
        from badking.storage import MemoryStorage

        storage = MemoryStorage()
        m1 = ChannelMonitor(storage=storage)
        m1.watch(-100)
        run(m1.record_join(-100, FakeUser(7, "سارا")))

        m2 = ChannelMonitor(storage=storage)
        m2.watch(-100)
        loaded = run(m2.load(-100))
        assert loaded == 1
        assert m2.events(-100)[0].name == "سارا"

    def test_load_without_storage(self):
        m = ChannelMonitor()
        assert run(m.load(-100)) == 0

    def test_load_missing_key(self):
        from badking.storage import MemoryStorage

        m = ChannelMonitor(storage=MemoryStorage())
        assert run(m.load(-100)) == 0

    def test_multiple_admins_one_channel(self):
        m = ChannelMonitor()
        m.watch(-100, admin_id=1)
        m.watch(-100, admin_id=2)
        assert m.admins_of(-100) == {1, 2}

    def test_one_admin_many_channels(self):
        m = ChannelMonitor()
        m.watch(-100, admin_id=1)
        m.watch(-200, admin_id=1)
        assert m.admins_of(-100) == {1}
        assert m.admins_of(-200) == {1}
