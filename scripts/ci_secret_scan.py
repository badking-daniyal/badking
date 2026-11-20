"""CI Secret Scanner — اسکن قطعی مخزن بدون چاپ هیچ Secret واقعی.

خروجی: فقط مسیر فایل + الگوی یافته + fingerprint هش کوتاه.
اگر Secret واقعی یافت شود، با exit code 1 CI را متوقف میکند.

استفاده:
    python scripts/ci_secret_scan.py
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT = os.environ.get("GIT_EXE", "git")

# الگوها — مقادیر NEVER چاپ نمیشوند
PATTERNS = {
    "BALE_TOKEN": re.compile(rb"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"),
    "PRIVATE_KEY": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS_KEY": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "JWT": re.compile(rb"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}

# مسیرهایی که عمداً fixture جعلی دارند (token نمونه مستندات / تست scanner)
ALLOWLIST = {
    "tests/test_security_scanner.py",
    "tests/test_doctor.py",
    "tests/test_resilience.py",
    "tests/test_secret_audit.py",
    "tests/fixtures",
    "START_HERE.md",
}


def tracked_files() -> list[str]:
    """فایلهای تحت کنترل git + فایلهای untracked (غیر ignore) را برگردان.

    اسکن فقط فایلهای tracked کافی نیست: یک فایل حاوی توکن میتواند قبل از
    commit هم در مخزن وجود داشته باشد. بنابراین untrackedها را هم اسکن میکنیم.
    """
    out = subprocess.run(
        [GIT, "ls-files"], cwd=ROOT, capture_output=True, text=True
    ).stdout
    extra = subprocess.run(
        [GIT, "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout
    names = set(line for line in out.splitlines() if line)
    names.update(line for line in extra.splitlines() if line)
    return sorted(names)


def main() -> int:
    findings = []
    for rel in tracked_files():
        if any(rel.startswith(a) or rel == a for a in ALLOWLIST):
            continue
        path = ROOT / rel
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        data = path.read_bytes()
        for label, pattern in PATTERNS.items():
            for m in pattern.findall(data):
                fp = hashlib.sha256(m).hexdigest()[:12]
                findings.append((rel, label, fp))

    if findings:
        print("CI SECRET SCAN: FAILED", file=sys.stderr)
        for rel, label, fp in findings:
            print(f"  {rel}: {label} fp={fp}", file=sys.stderr)
        return 1

    print(f"CI SECRET SCAN: OK ({len(tracked_files())} tracked files scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
