"""تست فایلهای گزارشی مأموریت."""

from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"

REPORTS = [
    "IMPLEMENTATION_STATUS.md",
    "SELF_CLIENT_AUDIT.md",
    "MIGRATION_VALIDATION.md",
    "REMAINING_GAPS.md",
]


def test_all_reports_exist():
    for name in REPORTS:
        assert (DOCS / name).is_file(), f"{name} وجود ندارد"


def test_reports_have_real_content():
    for name in REPORTS:
        text = (DOCS / name).read_text(encoding="utf-8")
        assert len(text) > 1000, f"{name} خیلی کوتاه است"
        assert text.startswith("# "), f"{name} عنوان ندارد"


def test_status_has_all_35_sections():
    text = (DOCS / "IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    for n in range(1, 36):
        assert f"| {n} |" in text, f"بخش {n} در وضعیت نیست"


def test_audit_labels_blocked():
    text = (DOCS / "SELF_CLIENT_AUDIT.md").read_text(encoding="utf-8")
    assert "BLOCKED" in text
    assert "PARTIALLY_VERIFIED" in text
    assert "_my_id" in text
    assert "kifpool" in text


def test_migration_report_has_real_numbers():
    text = (DOCS / "MIGRATION_VALIDATION.md").read_text(encoding="utf-8")
    assert "۴/۴" in text or "4/4" in text
    assert "BaleMethod" in text
    assert "BLOCKED" in text


def test_gaps_report_lists_all_categories():
    text = (DOCS / "REMAINING_GAPS.md").read_text(encoding="utf-8")
    for category in ("BLOCKED", "NOT_IMPLEMENTED", "PARTIALLY_IMPLEMENTED"):
        assert category in text


def test_no_fake_completion_claim():
    """گزارش نباید self-bot را کامل اعلام کند."""
    text = (DOCS / "IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    line = [l for l in text.splitlines() if l.startswith("| 6 |")][0]
    assert "PARTIALLY" in line or "BLOCKED" in line
