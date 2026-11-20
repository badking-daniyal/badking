"""تست مستندات مأموریت — اسناد جدید باید با کد واقعی هماهنگ باشند."""

from __future__ import annotations

import json
import re
from pathlib import Path

import badking

DOCS = Path(__file__).resolve().parents[1] / "docs"
REQUIRED = [
    "IMPLEMENTATION_STATUS.md",
    "MASTER_AUDIT_REPORT.md",
    "COMPETITIVE_ANALYSIS.md",
    "API_REFERENCE.md",
]


def test_required_docs_exist():
    for name in REQUIRED:
        assert (DOCS / name).is_file(), f"{name} وجود ندارد"


def test_status_doc_has_all_sections():
    text = (DOCS / "IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    for n in range(1, 36):
        assert f"| {n} |" in text, f"بخش {n} در وضعیت نیست"


def test_status_doc_uses_real_statuses():
    text = (DOCS / "IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    for status in ("IMPLEMENTED", "TESTED", "DOCUMENTED", "PARTIALLY_IMPLEMENTED", "NOT_IMPLEMENTED", "BLOCKED"):
        assert status in text


def test_audit_report_has_key_findings():
    text = (DOCS / "MASTER_AUDIT_REPORT.md").read_text(encoding="utf-8")
    for kw in ("bot.run()", "security scan", "mappings.json", "benchmark"):
        assert kw.lower() in text.lower(), f"{kw} در گزارش آودیت نیست"


def test_competitive_analysis_no_false_claims():
    text = (DOCS / "COMPETITIVE_ANALYSIS.md").read_text(encoding="utf-8")
    assert "تأییدنشده" in text
    assert "BLOCKED" in text


def test_api_reference_imports_exist():
    """هر import در API Reference باید واقعی باشد."""
    text = (DOCS / "API_REFERENCE.md").read_text(encoding="utf-8")
    for match in re.finditer(r"from badking(?:\.hybrid)? import ([^\n]+)", text):
        names = [n.strip() for n in match.group(1).split(",")]
        for name in names:
            if not name:
                continue
            assert hasattr(badking, name), f"badking.{name} وجود ندارد"


def test_api_reference_methods_exist():
    """متدهای ذکرشده در API Reference روی Bot یا SelfBot باشند."""
    from badking import Bot
    from badking.hybrid import SelfBot

    text = (DOCS / "API_REFERENCE.md").read_text(encoding="utf-8")

    bot_section = text.split("### متدهای پیام")[1].split("## Self Client")[0]
    bot_methods = re.findall(r"`(\w+)`", bot_section)
    for method in bot_methods:
        assert hasattr(Bot, method), f"Bot.{method} وجود ندارد"

    # عنوان «### متدها» چند بار تکرار شده؛ آنی را میخواهیم که بعد از
    # «## Self Client» و قبل از «## FSM» است.
    start = text.index("## Self Client")
    self_start = text.index("### متدها", start)
    self_section = text[self_start:text.index("## FSM", self_start)]
    self_methods = re.findall(r"`(\w+)`", self_section)
    for method in self_methods:
        assert hasattr(SelfBot, method), f"SelfBot.{method} وجود ندارد"


def test_mapping_json_valid():
    path = Path(__file__).resolve().parents[1] / "migration" / "mappings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["source"] == "aiobale"
    assert data["target"] == "badking"
    assert len(data["statuses"]) == 4
