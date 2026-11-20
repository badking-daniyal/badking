"""تست پنج فایل گزارش مرحله Real-World Validation."""

from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"

FILES = [
    "PROTOCOL_VERIFICATION.md",
    "REAL_WORLD_TESTING.md",
    "COMPETITIVE_BENCHMARK.md",
    "SECURITY_REVIEW.md",
    "IMPLEMENTATION_STATUS.md",
]


def test_all_reports_exist():
    for name in FILES:
        assert (DOCS / name).is_file(), f"{name} وجود ندارد"


def test_reports_have_content():
    for name in FILES:
        text = (DOCS / name).read_text(encoding="utf-8")
        assert len(text) > 800, f"{name} خیلی کوتاه است"


def test_protocol_report_has_real_numbers():
    text = (DOCS / "PROTOCOL_VERIFICATION.md").read_text(encoding="utf-8")
    assert "72 / 72" in text or "۷۲ / ۷۲" in text
    assert "aiobale 0.3.9" in text
    assert "BLOCKED" in text


def test_real_world_report_separates_mock_from_live():
    text = (DOCS / "REAL_WORLD_TESTING.md").read_text(encoding="utf-8")
    assert "MOCK" in text
    assert "LIVE" in text
    assert "BLOCKED" in text


def test_benchmark_report_is_honest():
    text = (DOCS / "COMPETITIVE_BENCHMARK.md").read_text(encoding="utf-8")
    assert "کندتر" in text or "slower" in text.lower()
    assert "BLOCKED" in text


def test_security_report_has_statuses():
    text = (DOCS / "SECURITY_REVIEW.md").read_text(encoding="utf-8")
    for status in ("PARTIALLY_IMPLEMENTED", "NOT_IMPLEMENTED", "IMPLEMENTED"):
        assert status in text


def test_status_has_current_count():
    text = (DOCS / "IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    assert "۱۲۵۹" in text
