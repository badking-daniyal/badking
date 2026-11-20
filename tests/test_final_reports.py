"""تست گزارشهای نهایی — وجود، محتوا و صداقت وضعیتها."""

from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"

REQUIRED = [
    "FINAL_SECURITY_REPORT.md",
    "SECRET_MANAGEMENT_AUDIT.md",
    "ACCESS_CONTROL_AUDIT.md",
    "FINAL_SERIALIZATION_BENCHMARK.md",
    "FINAL_MIGRATION_COMPATIBILITY.md",
    "FINAL_ENGINEERING_STATUS.md",
]


class TestFinalReports:
    def test_all_reports_exist(self):
        for name in REQUIRED:
            assert (DOCS / name).is_file(), name

    def test_reports_are_substantive(self):
        for name in REQUIRED:
            text = (DOCS / name).read_text(encoding="utf-8")
            assert len(text) > 800, f"{name} خیلی کوتاه است"

    def test_no_real_token_in_reports(self):
        import re

        token = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b")
        for name in REQUIRED:
            text = (DOCS / name).read_text(encoding="utf-8")
            # فقط نمونه مستندات مجاز است
            for m in token.findall(text):
                assert m.startswith("123456789:"), f"{name} حاوی توKEN واقعی است"

    def test_statuses_are_explicit(self):
        security = (DOCS / "FINAL_SECURITY_REPORT.md").read_text(encoding="utf-8")
        for status in ("NOT_IMPLEMENTED", "BLOCKED", "IMPLEMENTED"):
            assert status in security

        reliability = (DOCS / "SELF_CLIENT_RELIABILITY.md").read_text(encoding="utf-8")
        for status in ("IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "NOT_IMPLEMENTED", "BLOCKED"):
            assert status in reliability

    def test_engineering_status_answers_seven_questions(self):
        text = (DOCS / "FINAL_ENGINEERING_STATUS.md").read_text(encoding="utf-8")
        persian = "۱۲۳۴۵۶۷"
        for i in range(7):
            assert f"### {persian[i]}." in text or f"### {i + 1}." in text

    def test_no_pypi_publish_claim(self):
        text = (DOCS / "FINAL_ENGINEERING_STATUS.md").read_text(encoding="utf-8")
        assert "منتشر نشد" in text
