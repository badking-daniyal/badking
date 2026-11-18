"""تستهای فاز ۷: Observability، امنیت، Dry-run، Health."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking.observability import Metrics  # noqa: E402
from badking.security import AntiSpam, AuditLog, Captcha, RBAC, Secrets  # noqa: E402
from badking.testing import DryBot, Health  # noqa: E402


def test_metrics():
    m = Metrics()
    m.inc("messages_sent", 2, chat="private")
    m.inc("messages_sent", 1, chat="private")
    m.gauge("queue_size", 5)
    m.observe("latency", 0.25)
    text = m.render()
    assert "messages_sent" in text
    # prefix حالا اعمال میشود: نام متریکها badking_ میشود
    assert text.splitlines()[0] == "# TYPE badking_messages_sent counter"
    assert "badking_queue_size 5" in text
    assert "badking_latency_count 1" in text


def test_secrets_mask():
    assert Secrets.mask("123456:ABCdefGHI") == "1234********fGHI"
    assert Secrets.mask(None) == "<none>"


def test_antispam():
    spam = AntiSpam(max_messages=2, window_seconds=60, ban_seconds=0.1)
    assert spam.is_allowed(1)
    assert spam.is_allowed(1)
    assert not spam.is_allowed(1)  # سومی مسدود شد
    spam.block(2)
    assert not spam.is_allowed(2)


def test_captcha():
    cap = Captcha()
    q = cap.challenge(1)
    answer = str(eval(q.replace("= ؟", "").strip()))  # محاسبه ساده تست
    assert cap.verify(1, answer)
    assert not cap.verify(1, answer)  # دوبار نمیشود


def test_audit_and_rbac(tmp_path):
    log = AuditLog(str(tmp_path / "audit.log"))
    log.record("admin1", "broadcast", "all_users", count=10)
    assert log.list(actor="admin1")[0].action == "broadcast"
    assert (tmp_path / "audit.log").exists()

    rbac = RBAC()
    rbac.grant("admin", "broadcast")
    assert rbac.has("admin", "broadcast")
    assert not rbac.has("viewer", "broadcast")


def test_dry_bot():
    import asyncio

    bot = DryBot()
    asyncio.run(bot.send_message(123, "تست"))
    assert "تست" in bot.summary()


def test_health():
    h = Health()
    h.set("api", True)
    h.set("db", False)
    status = h.status()
    assert status.status == "degraded"
    assert status.as_dict()["checks"]["db"] is False
