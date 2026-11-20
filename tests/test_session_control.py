"""تست SessionManager و متدهای سطحبالای SelfBot.

همه آفلاین — transport تقلبی، بدون سرور بله و بدون شماره واقعی.
"""

from __future__ import annotations

import asyncio
import json
import zipfile

import pytest

from badking.hybrid import (
    CheckReport,
    CreateResult,
    SessionManager,
    SessionManagerError,
)
from badking.hybrid.client import Peer, SelfBot, SelfBotError
from badking.hybrid.session import Session


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _async(value):
    return value


def make_session(uid: int = 123, phone: str = "989123456789") -> Session:
    return Session(
        access_token="eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjk5OTk5OTk5OTl9.x",
        user_id=uid,
        phone=phone,
        name=f"کاربر {uid}",
    )


class FakeTransport:
    """Transport تقلبی: اتصال/بستن را شبیهسازی میکند."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.connected = False

    async def request(self, payload: bytes, timeout: float | None = None) -> bytes:
        return b""


# ---------- SessionManager: CRUD ----------

class TestSessionManagerBasics:
    def make(self, tmp_path, **kw):
        return SessionManager(tmp_path / "sessions.bks", **kw)

    def test_empty(self, tmp_path):
        m = self.make(tmp_path)
        assert m.count() == 0
        assert "هیچ اکنتی" in m.summary()

    def test_put_and_list(self, tmp_path):
        m = self.make(tmp_path)
        m.store.put(make_session(1, "989111111111"))
        m.store.put(make_session(2, "989222222222"))

        accounts = m.list_accounts()
        assert len(accounts) == 2
        assert {a.user_id for a in accounts} == {1, 2}

    def test_search_by_phone(self, tmp_path):
        m = self.make(tmp_path)
        m.store.put(make_session(1, "989111111111"))
        found = m.search("111111111")
        assert len(found) == 1
        assert found[0].user_id == 1

    def test_search_by_id(self, tmp_path):
        m = self.make(tmp_path)
        m.store.put(make_session(42, "989111111111"))
        found = m.search("42")
        assert len(found) == 1

    def test_search_by_name(self, tmp_path):
        m = self.make(tmp_path)
        m.store.put(make_session(1, "989111111111"))
        assert len(m.search("کاربر")) == 1

    def test_remove(self, tmp_path):
        m = self.make(tmp_path)
        key = m.store.put(make_session(1))
        assert m.remove(key) is True
        assert m.count() == 0

    def test_remove_missing(self, tmp_path):
        m = self.make(tmp_path)
        assert m.remove("nope") is False

    def test_clear(self, tmp_path):
        m = self.make(tmp_path)
        m.store.put(make_session(1))
        m.store.put(make_session(2))
        assert m.clear() == 2
        assert m.count() == 0

    def test_get(self, tmp_path):
        m = self.make(tmp_path)
        key = m.store.put(make_session(7))
        assert m.get(key).user_id == 7

    def test_summary(self, tmp_path):
        m = self.make(tmp_path)
        m.store.put(make_session(1))
        text = m.summary()
        assert "1 اکانت" in text
        assert "989123456789" in text


# ---------- بکاپ / ریستور ----------

class TestBackup:
    def make(self, tmp_path, name="s.bks"):
        return SessionManager(tmp_path / name, password="secret")

    def test_export_creates_zip(self, tmp_path):
        m = self.make(tmp_path)
        m.store.put(make_session(1))
        p = m.export_zip(tmp_path / "backup.zip")
        assert p.exists()
        assert zipfile.is_zipfile(p)

    def test_export_contains_manifest(self, tmp_path):
        m = self.make(tmp_path)
        m.store.put(make_session(1))
        p = m.export_zip(tmp_path / "backup.zip")
        with zipfile.ZipFile(p) as z:
            names = z.namelist()
            assert "sessions.bks" in names
            assert "manifest.json" in names
            manifest = json.loads(z.read("manifest.json"))
            assert manifest["count"] == 1
            assert len(manifest["sha256"]) == 64

    def test_roundtrip(self, tmp_path):
        m1 = self.make(tmp_path, "a.bks")
        m1.store.put(make_session(1, "989111111111"))
        m1.store.put(make_session(2, "989222222222"))
        backup = m1.export_zip(tmp_path / "backup.zip")

        m2 = self.make(tmp_path, "b.bks")
        imported = m2.import_zip(backup)
        assert imported == 2
        assert m2.count() == 2
        assert {a.user_id for a in m2.list_accounts()} == {1, 2}

    def test_merge_keeps_existing(self, tmp_path):
        m1 = self.make(tmp_path, "a.bks")
        m1.store.put(make_session(1))
        backup = m1.export_zip(tmp_path / "backup.zip")

        m2 = self.make(tmp_path, "b.bks")
        m2.store.put(make_session(99))
        m2.import_zip(backup)
        assert m2.count() == 2

    def test_corrupt_hash_rejected(self, tmp_path):
        m = self.make(tmp_path)
        m.store.put(make_session(1))
        p = m.export_zip(tmp_path / "backup.zip")

        with zipfile.ZipFile(p) as z:
            files = {n: z.read(n) for n in z.namelist()}
        manifest = json.loads(files["manifest.json"])
        manifest["sha256"] = "0" * 64
        with zipfile.ZipFile(p, "w") as z:
            for n, data in files.items():
                z.writestr(n, json.dumps(manifest) if n == "manifest.json" else data)

        with pytest.raises(SessionManagerError) as info:
            m.import_zip(p)
        assert "هش" in str(info.value)

    def test_missing_file(self, tmp_path):
        m = self.make(tmp_path)
        with pytest.raises(SessionManagerError) as info:
            m.import_zip(tmp_path / "nope.zip")
        assert "پیدا نشد" in str(info.value)

    def test_bad_zip(self, tmp_path):
        m = self.make(tmp_path)
        bad = tmp_path / "bad.zip"
        bad.write_bytes(b"not a zip")
        with pytest.raises(SessionManagerError) as info:
            m.import_zip(bad)
        assert "خراب" in str(info.value)

    def test_legacy_bale_import(self, tmp_path):
        """بکاپ قدیمی با فایل .bale داخل sessions/."""
        m = self.make(tmp_path, "fresh.bks")
        p = tmp_path / "old.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("sessions/989111111111.bale", json.dumps(make_session(5).to_dict()))
            z.writestr("sessions/broken.bale", "not json")

        imported = m.import_zip(p)
        assert imported == 1
        assert m.count() == 1

    def test_zip_without_sessions_rejected(self, tmp_path):
        m = self.make(tmp_path)
        p = tmp_path / "empty.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("readme.txt", "hello")
        with pytest.raises(SessionManagerError):
            m.import_zip(p)


# ---------- ساخت سشن ----------

class TestCreateSession:
    def test_invalid_phone(self, tmp_path):
        m = SessionManager(tmp_path / "s.bks")
        result = run(m.request_code("abc"))
        assert result.ok is False
        assert "شماره" in result.message

    def test_existing_session_skips_code(self, tmp_path):
        m = SessionManager(tmp_path / "s.bks")
        m.store.put(make_session(1, "989111111111"))
        result = run(m.request_code("09111111111"))
        assert result.ok is True
        assert result.needs_code is False
        assert "از قبل" in result.message

    def test_submit_without_request(self, tmp_path):
        m = SessionManager(tmp_path / "s.bks")
        result = run(m.submit_code("09123456789", "12345"))
        assert result.ok is False
        assert "request_code" in result.message

    def test_result_to_dict(self):
        r = CreateResult(ok=True, message="خوب", needs_code=True)
        d = r.to_dict()
        assert d["ok"] is True
        assert d["needs_code"] is True


# ---------- متدهای SelfBot ----------

class TestSelfBotHighLevel:
    """منطق متدهای سطحبالا را با patch کردن call() میسنجیم."""

    def make(self, responses: dict):
        calls: list[tuple[str, dict]] = []

        async def fake_call(full_name: str, **kwargs):
            calls.append((full_name, kwargs))
            return responses.get(full_name, {})

        bot = SelfBot(session=make_session())
        bot.call = fake_call  # type: ignore[method-assign]
        return bot, calls

    def test_get_wallet_uses_abacus(self):
        bot, calls = self.make({"abacus.GetMyKifpools": {"wallet": {"balance": 5000}}})
        result = run(bot.get_wallet())
        assert result["balance"] == 5000
        assert bot.wallet_balance(result) == 5000
        assert calls[0][0] == "abacus.GetMyKifpools"

    def test_get_wallet_empty(self):
        bot, calls = self.make({"abacus.GetMyKifpools": {}})
        assert run(bot.get_wallet())["balance"] == 0

    def test_wallet_balance_requires_arg(self):
        bot, _ = self.make({})
        with pytest.raises(ValueError):
            bot.wallet_balance()

    def test_get_full_me(self):
        bot, _ = self.make({})
        bot.get_me = lambda: _async(Peer(id=123, title="علی"))  # type: ignore[assignment]
        me = run(bot.get_full_me())
        assert me["id"] == 123
        assert me["name"] == "علی"
        assert me["phone"] == "989123456789"

    def test_get_group_preview(self):
        bot, calls = self.make(
            {"groups.GetGroupPreview": {"group": {"id": 99, "title": "گروه", "isJoined": 1}}}
        )
        info = run(bot.get_group_preview("https://ble.ir/join/AbCd123"))
        assert info["id"] == 99
        assert info["title"] == "گروه"
        assert info["is_joined"] is True
        assert calls[0][1]["token"] == "AbCd123"

    def test_get_group_preview_bad_link(self):
        bot, _ = self.make({})
        with pytest.raises(SelfBotError) as info:
            run(bot.get_group_preview("not a link!!"))
        assert "لینک" in str(info.value)

    def test_join_by_link(self):
        bot, calls = self.make({"groups.JoinGroup": {"ok": 1}})
        run(bot.join_by_link("https://ble.ir/join/XYZ"))
        assert calls[0][0] == "groups.JoinGroup"
        assert calls[0][1]["token"] == "XYZ"

    def test_leave_by_id(self):
        bot, calls = self.make({"groups.LeaveGroup": {"ok": 1}})
        assert run(bot.leave_by_id(12345)) is True
        assert calls[0][0] == "groups.LeaveGroup"
        assert calls[0][1]["group"]["id"] == 12345

    def test_report_chat(self):
        bot, calls = self.make({"report.ReportInappropriateContent": {"ok": 1}})
        assert run(bot.report_chat(999, 3, "اسپم")) is True
        assert calls[0][0] == "report.ReportInappropriateContent"
        body = calls[0][1]["report_body"]
        assert body["peer"]["id"] == 999
        assert body["kind"] == "اسپم"

    def test_upvote(self):
        bot, calls = self.make({"magazine.UpvotePost": {"ok": 1}})
        bot.get_entity = lambda ref: _async(Peer(id=123, type="chat"))  # type: ignore[assignment]
        assert run(bot.upvote(123, 5)) is True
        assert calls[0][0] == "magazine.UpvotePost"

    def test_set_reaction_delegates(self):
        bot, _ = self.make({})
        seen = []

        async def fake_react(ref, mid, code):
            seen.append((ref, mid, code))
            return True

        bot.react = fake_react  # type: ignore[method-assign]
        assert run(bot.set_reaction(1, 2, "❤️")) is True
        assert seen == [(1, 2, "❤️")]

    def test_transport_factory_used(self):
        t = FakeTransport()
        bot = SelfBot(session=make_session(), transport_factory=lambda: t)
        run(bot.connect())
        assert bot._transport is t


# ---------- CheckReport ----------

class TestCheckReport:
    def test_summary(self):
        r = CheckReport(total=5, healthy=3, broken=["a"], duplicates=["b"])
        text = r.summary
        assert "5 اکانت" in text
        assert "3 سالم" in text

    def test_to_dict(self):
        r = CheckReport(total=1, healthy=1)
        assert r.to_dict()["total"] == 1
