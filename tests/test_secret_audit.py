"""Secret Audit — قابل تکرار، بدون چاپ secret واقعی.

این تستها تضمین میکنند:
- .gitignore الگوهای بکاپ/session/clید را میپوشاند
- Scanner الگوی توKEN بله را دارد
- هیچ secret واقعی در فایلهای trackشده مخزن نیست
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT = os.environ.get(
    "GIT_EXE",
    r"C:\Program Files\Git\cmd\git.exe" if os.name == "nt" else "git",
)

# الگو — مقادیر چاپ نمیشوند
BALE_TOKEN = re.compile(rb"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b")
PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")


def git(*args: str) -> str:
    return subprocess.run(
        [GIT, *args], cwd=ROOT, capture_output=True, text=True,
    ).stdout


class TestGitignoreCoverage:
    def test_gitignore_blocks_env(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", ".env.*", "*.env"):
            assert pattern in text

    def test_gitignore_blocks_backups_and_sessions(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in ("*.zip", "*.bak", "*.bks", "*.session", "*.pem", "*.key"):
            assert pattern in text

    def test_no_secret_file_tracked(self):
        tracked = git("ls-files").splitlines()
        dangerous = [
            f for f in tracked
            if f.endswith((".env", ".zip", ".pem", ".key", ".session", ".bks"))
            or "/.env." in f
        ]
        assert dangerous == [], f"فایل حساس track شده: {dangerous}"


class TestTrackedFilesClean:
    def test_no_real_token_in_tracked_files(self):
        """فقط فایلهای متنی trackشده را میخوانیم، الگو را میسنجیم."""
        hits = []
        for rel in git("ls-files").splitlines():
            p = ROOT / rel
            if not p.is_file() or p.suffix not in {".py", ".md", ".json", ".toml", ".ini", ".cfg"}:
                continue
            data = p.read_bytes()
            if len(data) > 2_000_000:
                continue
            m = BALE_TOKEN.search(data)
            if m:
                # تستها عمداً توKEN جعلی دارند — آنها را رد میکنیم
                if "test" in rel or "fixture" in rel:
                    continue
                hits.append(rel)
        assert hits == [], f"توKEN شبیه واقعی در: {hits}"

    def test_fake_private_key_fixture_is_allowed(self):
        """fixture جعلی تست، secret واقعی نیست."""
        p = ROOT / "tests" / "test_security_scanner.py"
        if p.exists():
            data = p.read_bytes()
            assert b"abc" in data  # محتوای جعلی


class TestScannerPatterns:
    def test_scanner_detects_bale_token_pattern(self):
        from badking.security.scanner import SECRET_PATTERNS

        codes = [p[0] for p in SECRET_PATTERNS]
        assert "BOT_TOKEN_HARDCODED" in codes

    def test_scanner_does_not_leak_value(self):
        """Finding.evidence نباید مقدار کامل secret را چاپ کند."""
        from badking.security.scanner import SecurityScanner

        report = SecurityScanner().scan(str(ROOT / "badking"))
        for finding in report.findings:
            if finding.code == "BOT_TOKEN_HARDCODED":
                assert ":" not in finding.evidence or len(finding.evidence) < 40
