"""Security Scanner — پیدا کردن مشکلات امنیتی در پروژه بله.

    from badking.security import SecurityScanner

    scanner = SecurityScanner()
    report = scanner.scan(".")
    print(report.summary())

    # یا از CLI:
    #   badking security scan .

قواعد صادقانه:
- هر یافته با خط و متن دقیق کد برمیگردد.
- چیزی را «آسیبپذیری» مینامیم که واقعاً الگوی خطرناک باشد.
- فایلهای `.env` و secretها را اسکن میکنیم ولی محتوای secret را در
  خروجی چاپ نمیکنیم — فقط میگوییم «در فلان خط یک توکن هست».
- نتیجه CRITICAL/HIGH/MEDIUM/LOW/INFO است، همانطور که سند خواسته.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# ---------- Severity ----------

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def severity_rank(name: str) -> int:
    """عدد کوچکتر = جدیتر."""
    try:
        return SEVERITY_ORDER.index(name.upper())
    except ValueError:
        return len(SEVERITY_ORDER)


@dataclass
class Finding:
    """یک یافته امنیتی."""

    severity: str
    code: str
    message: str
    path: str
    line: int = 0
    evidence: str = ""
    hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "line": self.line,
            "evidence": self.evidence,
            "hint": self.hint,
        }

    def __str__(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"[{self.severity}] {self.code} — {self.message} ({location})"


@dataclass
class ScanReport:
    """نتیجه اسکن."""

    root: str
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0

    def by_severity(self, severity: str) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity.upper()]

    def counts(self) -> dict[str, int]:
        return {s: len(self.by_severity(s)) for s in SEVERITY_ORDER}

    @property
    def critical_count(self) -> int:
        return len(self.by_severity("CRITICAL"))

    def summary(self) -> str:
        counts = self.counts()
        lines = [
            f"اسکن امنیتی: {self.root}",
            f"  فایلهای بررسیشده: {self.files_scanned}",
            f"  یافتهها: {len(self.findings)}",
        ]
        for sev in SEVERITY_ORDER:
            if counts[sev]:
                lines.append(f"    {sev}: {counts[sev]}")
        if not self.findings:
            lines.append("  ✅ مشکلی پیدا نشد.")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "files_scanned": self.files_scanned,
            "files_skipped": self.files_skipped,
            "counts": self.counts(),
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------- الگوها ----------

# الگوهایی که نشاندهنده secret واقعیاند
SECRET_PATTERNS: list[tuple[str, str, str, str]] = [
    (
        "BOT_TOKEN_HARDCODED",
        r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b",
        "CRITICAL",
        "توکن ربات در سورس کد پیدا شد. آن را از محیط بخوان.",
    ),
    (
        "AWS_ACCESS_KEY",
        r"\bAKIA[0-9A-Z]{16}\b",
        "CRITICAL",
        "کلید AWS در کد پیدا شد.",
    ),
    (
        "PRIVATE_KEY",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "CRITICAL",
        "کلید خصوصی در فایل پیدا شد.",
    ),
    (
        "GENERIC_API_KEY",
        r"(?:api[_-]?key|secret|password)\s*=\s*[\"'][A-Za-z0-9_\-]{16,}[\"']",
        "HIGH",
        "رشته شبیه کلید API بهصورت ثابت در کد است.",
    ),
    (
        "PHONE_NUMBER",
        r"\b9\d{9}\b",
        "LOW",
        "شماره تلفن در کد پیدا شد — ممکن است داده شخصی باشد.",
    ),
]

# الگوهای کد ناامن
UNSAFE_PATTERNS: list[tuple[str, str, str, str]] = [
    (
        "EVAL_USAGE",
        r"\beval\s*\(",
        "CRITICAL",
        "eval() میتواند کد دلخواه اجرا کند.",
    ),
    (
        "EXEC_USAGE",
        r"\bexec\s*\(",
        "CRITICAL",
        "exec() میتواند کد دلخواه اجرا کند.",
    ),
    (
        "SHELL_TRUE",
        r"subprocess\.\w+\([^)]*shell\s*=\s*True",
        "HIGH",
        "اجرای دستور با shell=True خطر تزریق دستور دارد.",
    ),
    (
        "SSL_DISABLED",
        r"verify\s*=\s*False",
        "HIGH",
        "غیرفعال کردن verify SSL ترافیک را در معرض MITM میگذارد.",
    ),
    (
        "WILDCARD_IMPORT",
        r"from\s+\S+\s+import\s+\*",
        "LOW",
        "import * خوانایی را کم و تداخل نامها را ممکن میکند.",
    ),
    (
        "BARE_EXCEPT",
        r"^\s*except\s*:",
        "MEDIUM",
        "except بدون نوع، خطاهای واقعی را پنهان میکند.",
    ),
    (
        "DEBUG_TRUE",
        r"(?:debug|DEBUG)\s*=\s*True",
        "MEDIUM",
        "حالت debug در تنظیمات فعال است.",
    ),
]

# الگوهای تنظیمات ناامن
INSECURE_CONFIG: list[tuple[str, str, str, str]] = [
    (
        "WORLD_READABLE_SECRET",
        r"chmod\s+777|0o777",
        "HIGH",
        "دسترس جهانی به فایل secret داده شده است.",
    ),
    (
        "ALLOW_ALL_HOSTS",
        r"ALLOWED_HOSTS\s*=\s*\[?\s*[\"']\*[\"']",
        "MEDIUM",
        "همه hostها مجازاند.",
    ),
]

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}


class SecurityScanner:
    """اسکنر امنیتی پروژه.

    Args:
        max_file_size: فایلهای بزرگتر از این نادیده میشوند (به بایت).
        include_patterns: الگوهای فایل برای اسکن. پیشفرض کد و تنظیمات.
    """

    def __init__(
        self,
        *,
        max_file_size: int = 2 * 1024 * 1024,
        include_patterns: Iterable[str] | None = None,
    ) -> None:
        self.max_file_size = max_file_size
        self.patterns = list(include_patterns or [
            "*.py", "*.js", "*.ts", "*.json", "*.yaml", "*.yml",
            "*.toml", "*.ini", "*.cfg", "*.env", "*.sh", "*.ps1",
            ".env", ".env.*",
        ])

    # ---------- اسکن ----------

    def scan(self, root: str | Path) -> ScanReport:
        """پوشه را اسکن میکند."""
        root = Path(root)
        if not root.exists():
            return ScanReport(root=str(root))

        report = ScanReport(root=str(root))
        seen: set[Path] = set()

        for pattern in self.patterns:
            for path in root.rglob(pattern):
                if not path.is_file() or path in seen:
                    continue
                seen.add(path)

                if any(part in SKIP_DIRS for part in path.parts):
                    report.files_skipped += 1
                    continue

                try:
                    if path.stat().st_size > self.max_file_size:
                        report.files_skipped += 1
                        continue
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    report.files_skipped += 1
                    continue

                report.files_scanned += 1
                report.findings.extend(self._scan_text(text, str(path)))

        # مرتب بر اساس severity
        report.findings.sort(key=lambda f: (severity_rank(f.severity), f.path, f.line))
        return report

    def scan_file(self, path: str | Path) -> ScanReport:
        """یک فایل را اسکن میکند."""
        path = Path(path)
        report = ScanReport(root=str(path))
        if not path.is_file():
            return report

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return report

        report.files_scanned = 1
        report.findings.extend(self._scan_text(text, str(path)))
        report.findings.sort(key=lambda f: severity_rank(f.severity))
        return report

    # ---------- متن ----------

    def _scan_text(self, text: str, path: str) -> list[Finding]:
        findings: list[Finding] = []
        lines = text.splitlines()

        # خطوطی که خودِ تعریف الگوهااند (مثلاً رشته "eval(" در scanner)
        # نباید بهعنوان یافته شمرده شوند. این خطوط را با AST پیدا میکنیم.
        pattern_lines = self._pattern_definition_lines(text)

        for index, line in enumerate(lines, 1):
            if index in pattern_lines:
                continue

            stripped = line.strip()

            # خطوط کامنت و رشته مستند را برای الگوهای کد نادیده میگیریم
            is_comment = stripped.startswith("#") or stripped.startswith("//")

            # secretها حتی در کامنت هم مهماند
            for code, pattern, sev, hint in SECRET_PATTERNS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    findings.append(
                        Finding(
                            severity=sev,
                            code=code,
                            message=hint,
                            path=path,
                            line=index,
                            evidence=self._redact(match.group(0)),
                            hint="مقدار را به متغیر محیطی منتقل کن.",
                        )
                    )

            if is_comment:
                continue

            for code, pattern, sev, hint in UNSAFE_PATTERNS:
                # eval/exec را با AST میگیریم تا رشتههای توضیحی (مثل متن
                # پیام همین scanner) بهعنوان یافته شمرده نشوند.
                if code in {"EVAL_USAGE", "EXEC_USAGE"}:
                    continue
                if re.search(pattern, line, re.IGNORECASE | re.MULTILINE):
                    findings.append(
                        Finding(
                            severity=sev,
                            code=code,
                            message=hint,
                            path=path,
                            line=index,
                            evidence=stripped[:120],
                            hint="از جایگزین امنتر استفاده کن.",
                        )
                    )

            for code, pattern, sev, hint in INSECURE_CONFIG:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            severity=sev,
                            code=code,
                            message=hint,
                            path=path,
                            line=index,
                            evidence=stripped[:120],
                        )
                    )

        # بررسی AST برای مواردی که regex کافی نیست
        if path.endswith(".py"):
            findings.extend(self._scan_ast(text, path))

        return findings

    def _pattern_definition_lines(self, text: str) -> set[int]:
        """خطوطی که رشته الگو تعریف میکنند، برای جلوگیری از false positive.

        وقتی scanner خودش را اسکن میکند، رشته ``"eval("`` در لیست الگوها
        نباید بهعنوان استفاده از eval شمرده شود. هر رشتهای که درون یک
        tuple در سطح ماژول (مانند SECRET_PATTERNS) است را پیدا میکنیم.
        """
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return set()

        lines: set[int] = set()
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]

            if any(
                name in {"SECRET_PATTERNS", "UNSAFE_PATTERNS", "INSECURE_CONFIG"}
                for name in targets
            ) and node.value is not None:
                for child in ast.walk(node.value):
                    line = getattr(child, "lineno", 0)
                    if line:
                        lines.add(line)
        return lines

    def _scan_ast(self, text: str, path: str) -> list[Finding]:
        """یافتههایی که فقط با AST قابل تشخیصاند."""
        findings: list[Finding] = []
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            # eval/exec واقعی (نه رشته) — با AST، بدون false positive
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec"}:
                    code = "EVAL_USAGE" if node.func.id == "eval" else "EXEC_USAGE"
                    findings.append(
                        Finding(
                            severity="CRITICAL",
                            code=code,
                            message=f"{node.func.id}() میتواند کد دلخواه اجرا کند.",
                            path=path,
                            line=getattr(node, "lineno", 0),
                            hint="از جایگزین امنتر استفاده کن.",
                        )
                    )

            # assert در کد production
            if isinstance(node, ast.Assert):
                findings.append(
                    Finding(
                        severity="LOW",
                        code="ASSERT_IN_CODE",
                        message="assert در کد production با -O حذف میشود.",
                        path=path,
                        line=getattr(node, "lineno", 0),
                        hint="به جای assert از raise یا validation استفاده کن.",
                    )
                )

            # try: ... except Exception: pass
            if isinstance(node, ast.ExceptHandler):
                body = node.body
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    findings.append(
                        Finding(
                            severity="MEDIUM",
                            code="SILENT_EXCEPTION",
                            message="استثنا با pass پنهان شده است.",
                            path=path,
                            line=getattr(node, "lineno", 0),
                            hint="خطا را لاگ کن یا دوباره پرتاب کن.",
                        )
                    )

        return findings

    @staticmethod
    def _redact(value: str) -> str:
        """محو کردن مقدار secret در خروجی."""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:3]}{'*' * 6}{value[-3:]}"


__all__ = [
    "Finding",
    "SEVERITY_ORDER",
    "ScanReport",
    "SecurityScanner",
    "severity_rank",
]
