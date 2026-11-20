"""تست پنج فایل REPORT مرحله Optimization & Security Hardening."""

from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"

FILES = [
    "SECURITY_HARDENING.md",
    "PERFORMANCE_OPTIMIZATION.md",
    "SELF_CLIENT_RELIABILITY.md",
    "MIGRATION_RUNTIME_STATUS.md",
    "IMPLEMENTATION_STATUS.md",
]


def test_all_reports_exist():
    for name in FILES:
        assert (DOCS / name).is_file(), f"{name} وجود ندارد"


def test_reports_have_content():
    for name in FILES:
        assert len((DOCS / name).read_text(encoding="utf-8")) > 1000


def test_security_report_has_no_real_secret():
    """گزارش نباید الگوی توKEN واقعی چاپ کند."""
    import re

    text = (DOCS / "SECURITY_HARDENING.md").read_text(encoding="utf-8")
    # fingerprintها مجازاند، ولی الگوی کامل توKEN نباید باشد
    assert not re.search(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b", text)


def test_performance_report_has_real_numbers():
    text = (DOCS / "PERFORMANCE_OPTIMIZATION.md").read_text(encoding="utf-8")
    assert "0.004838" in text
    assert "0.008039" in text
    assert "۷۰۰" in text or "700" in text


def test_reliability_report_statuses():
    text = (DOCS / "SELF_CLIENT_RELIABILITY.md").read_text(encoding="utf-8")
    for status in ("IMPLEMENTED", "NOT_IMPLEMENTED", "BLOCKED"):
        assert status in text


def test_migration_report_is_honest():
    text = (DOCS / "MIGRATION_RUNTIME_STATUS.md").read_text(encoding="utf-8")
    assert "فقط Import" in text or "فقط import" in text
    assert "NOT_IMPLEMENTED" in text
