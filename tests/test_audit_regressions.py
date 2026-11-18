"""تست رگرسیون برای یافتههای ممیزی (امنیت، هسته، تخصصی)."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from badking.connectors.http import Connector  # noqa: E402
from badking.core.bot import Bot  # noqa: E402
from badking.core.constants import Limits  # noqa: E402
from badking.core.errors import StopPropagation  # noqa: E402
from badking.core.dispatcher import Dispatcher  # noqa: E402
from badking.events.bus import EventBus  # noqa: E402
from badking.filters.magic import F  # noqa: E402
from badking.fsm.fsm import State, StatesGroup  # noqa: E402
from badking.observability.metrics import Metrics  # noqa: E402
from badking.orm.store import Store  # noqa: E402
from badking.recovery.offset import OffsetStore  # noqa: E402
from badking.security.audit import AuditLog  # noqa: E402
from badking.security.antispam import AntiSpam  # noqa: E402
from badking.types import Update  # noqa: E402


# ---------- Store SQL injection ----------
def test_store_rejects_bad_table_name(tmp_path):
    with pytest.raises(ValueError):
        Store(str(tmp_path / "x.db"), table="bad; DROP TABLE x--")


def test_store_accepts_good_table_name(tmp_path):
    s = Store(str(tmp_path / "x.db"), table="valid_table_1")
    s.put("a", {"x": 1})
    assert s.get("a") == {"x": 1}


# ---------- AuditLog reload + limit ----------
def test_audit_reload(tmp_path):
    p = str(tmp_path / "audit.jsonl")
    l1 = AuditLog(p)
    l1.record("ali", "login", "system")
    l2 = AuditLog(p)
    assert len(l2.list()) == 1
    assert l2.list()[0].actor == "ali"


def test_audit_limit_zero(tmp_path):
    log = AuditLog(str(tmp_path / "a.jsonl"))
    log.record("a", "x")
    assert log.list(limit=0) == []


# ---------- Antispam ----------
def test_antispam_ban_does_not_reset_window():
    spam = AntiSpam(max_messages=2, window_seconds=60.0, ban_seconds=0.01)
    assert spam.is_allowed(1) is True
    assert spam.is_allowed(1) is True
    assert spam.is_allowed(1) is False  # بن میشود
    time.sleep(0.02)
    # بعد از بن، نباید دوباره سهمیه کامل بگیرد (هنوز داخل پنجره 60 ثانیهای)
    assert spam.is_allowed(1) is False


# ---------- Metrics ----------
def test_metrics_single_type_line():
    m = Metrics()
    m.inc("x", 1, kind="a")
    m.inc("x", 1, kind="b")
    out = m.render()
    assert out.count("# TYPE badking_x counter") == 1


def test_metrics_escapes_labels():
    m = Metrics()
    m.inc("x", 1, path='a"b')
    out = m.render()
    assert 'path="a\\"b"' in out


def test_metrics_prefix():
    m = Metrics(prefix="myshop")
    m.inc("orders")
    assert "myshop_orders" in m.render()


# ---------- EventBus isolation ----------
def test_event_bus_isolates_handler_errors():
    bus = EventBus()
    called = []

    async def bad(**kw):
        raise RuntimeError("boom")

    async def good(**kw):
        called.append(1)

    bus.subscribe("e", bad)
    bus.subscribe("e", good)
    asyncio.run(bus.emit("e"))
    assert called == [1]


# ---------- OffsetStore atomic ----------
def test_offset_store_roundtrip(tmp_path):
    s = OffsetStore(str(tmp_path / "off.json"))
    s.save(42)
    assert s.load() == 42
    assert not (tmp_path / "off.json.tmp").exists()


# ---------- Connector retries=0 ----------
def test_connector_retries_zero_still_requests():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"ok": True})

    c = Connector(base_url="http://example.com", retries=0,
                  client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    asyncio.run(c.get("/"))
    assert len(calls) == 1


# ---------- Limits calibration ----------
def test_limits_calibration_fractional():
    lim = Limits()
    lim.calibrate_from_response(3.0, 429)
    assert lim.rate_per_second == 1  # floor(1/3) => 1 (حداقل)
    assert lim.observed["retry_after_seconds"] == 3.0


# ---------- FSM inheritance ----------
def test_states_group_inheritance():
    class Base(StatesGroup):
        a = State()

    class Child(Base):
        b = State()

    assert "a" in Child.__states__
    assert "b" in Child.__states__


# ---------- F.contains safe ----------
def test_f_contains_non_string():
    from badking.types.message import Message
    # فیلتر نباید استثنا بدهد؛ فقط False برگرداند
    pred = F.text.contains("x")
    assert pred(object()) is False


# ---------- Dispatcher default storage ----------
def test_dispatcher_has_default_storage():
    dp = Dispatcher()
    assert dp.storage is not None


# ---------- StopPropagation export ----------
def test_stop_propagation_export():
    from badking import StopPropagation as SP
    assert SP is StopPropagation


# ---------- get_updates does not advance offset early ----------
def test_get_updates_no_early_offset():
    def handler(request):
        return httpx.Response(200, json={"ok": True, "result": [
            {"update_id": 10, "message": {"message_id": 1, "date": 1,
             "chat": {"id": 1, "type": "private"},
             "from": {"id": 1, "is_bot": False, "first_name": "x"}, "text": "hi"}}
        ]})

    bot = Bot("1:X", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    updates = asyncio.run(bot.get_updates())
    assert len(updates) == 1
    assert bot._offset == 0  # نباید پیشروی کرده باشد
