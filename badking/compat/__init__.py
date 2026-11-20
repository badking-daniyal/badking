"""Migration Toolkit — مهاجرت از aiobale به BADKING.

    from badking.compat import migrate_file, MigrationReport

    report = migrate_file("bot.py")
    print(report.summary())

    # یا از CLI:
    #   badking migrate bot.py
    #   badking migrate . --dry-run

قاعده صادقانه: هر چیزی که قابل نگاشت نیست، در گزارش می‌آید. هیچ
تبدیلی را «حدس» نمی‌زنیم. اگر مطمئن نیستیم، فایل دست‌نخورده می‌ماند و
گزارش می‌گوید چرا.

این ماژول کد را اجرا نمی‌کند، فقط AST را می‌خواند و تغییر می‌دهد.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("badking.compat")

from .bale_method import BaleMethod


# ---------- نگاشت اسم‌ها ----------

# import مستقیم: aiobale.X → badking.Y
IMPORT_MAP: dict[str, str] = {
    "Client": "Bot",
    "BaleClient": "Bot",
    "Bot": "Bot",
    "BaleMethod": "BaleMethod",
    "Dispatcher": "Dispatcher",
    "Router": "Router",
    "Message": "Message",
    "CallbackQuery": "CallbackQuery",
    "InlineKeyboardMarkup": "InlineKeyboardMarkup",
    "ReplyKeyboardMarkup": "ReplyKeyboardMarkup",
    "InlineKeyboardButton": "InlineKeyboardButton",
    "KeyboardButton": "KeyboardButton",
    "FSMContext": "FSMContext",
    "State": "State",
    "StatesGroup": "StatesGroup",
    "MemoryStorage": "MemoryStorage",
    "SQLiteStorage": "SQLiteStorage",
    "F": "F",
    "BaseMiddleware": "BaseMiddleware",
}

# متدهایی که اسمشان عوض شده: aiobale → badking
METHOD_MAP: dict[str, str] = {
    "answer": "reply",
    "answer_photo": "send_photo",
    "answer_document": "send_document",
    "answer_video": "send_video",
    "answer_audio": "send_audio",
    "answer_location": "send_location",
    "answer_contact": "send_contact",
    "answer_poll": "send_poll",
    "edit_message_reply_markup": "edit_message_reply_markup",
    "delete": "delete",
}

# متدهایی که در BADKING معادل ندارند — گزارش می‌شوند، تبدیل نمی‌شوند
UNSUPPORTED: dict[str, str] = {
    "get_updates_long_polling": "در BADKING با bot.run() جایگزین می‌شود",
    "register_next_step_handler": "در BADKING از FSM استفاده کن",
    "add_handler": "در BADKING با دکوراتور @router.message ثبت کن",
}


class MigrationError(Exception):
    """خطای مهاجرت، با راهنمای رفع."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message}\n  → {self.hint}" if self.hint else self.message


@dataclass
class Change:
    """یک تغییر انجام‌شده یا پیشنهادی."""

    line: int
    kind: str  # "import" | "method" | "unsupported" | "warning"
    before: str
    after: str = ""
    note: str = ""

    def __str__(self) -> str:
        if self.after:
            return f"خط {self.line}: {self.before} → {self.after}"
        return f"خط {self.line}: {self.before} ({self.note})"


@dataclass
class MigrationReport:
    """نتیجه مهاجرت یک فایل."""

    path: str
    changes: list[Change] = field(default_factory=list)
    unsupported: list[Change] = field(default_factory=list)
    warnings: list[Change] = field(default_factory=list)
    migrated: str = ""
    ok: bool = True
    error: str = ""

    @property
    def total(self) -> int:
        return len(self.changes)

    @property
    def needs_manual_work(self) -> bool:
        """آیا چیزی هست که خودکار نشد؟"""
        return bool(self.unsupported or self.warnings)

    def summary(self) -> str:
        """خلاصه خوانا."""
        lines = [f"{self.path}"]

        if not self.ok:
            lines.append(f"  ✗ خطا: {self.error}")
            return "\n".join(lines)

        if self.changes:
            lines.append(f"  ✓ {len(self.changes)} تغییر خودکار")
            for change in self.changes[:10]:
                lines.append(f"      {change}")
            if len(self.changes) > 10:
                lines.append(f"      ... و {len(self.changes) - 10} مورد دیگر")

        if self.unsupported:
            lines.append(f"  ⚠ {len(self.unsupported)} مورد نیاز به کار دستی")
            for item in self.unsupported:
                lines.append(f"      {item}")

        if self.warnings:
            lines.append(f"  ? {len(self.warnings)} هشدار")
            for item in self.warnings:
                lines.append(f"      {item}")

        if not self.changes and not self.needs_manual_work:
            lines.append("  — چیزی برای تغییر نبود")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ok": self.ok,
            "error": self.error,
            "changes": [
                {"line": c.line, "kind": c.kind, "before": c.before, "after": c.after}
                for c in self.changes
            ],
            "unsupported": [
                {"line": c.line, "name": c.before, "note": c.note}
                for c in self.unsupported
            ],
            "warnings": [
                {"line": c.line, "text": c.before, "note": c.note}
                for c in self.warnings
            ],
        }


def _line_of(source: str, node: ast.AST) -> int:
    return getattr(node, "lineno", 0)


def analyze(source: str, path: str = "<string>") -> MigrationReport:
    """فایل را می‌خواند و تغییرات لازم را پیدا می‌کند. چیزی نمی‌نویسد."""
    report = MigrationReport(path=path)

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        report.ok = False
        report.error = f"خطای نحوی در خط {exc.lineno}: {exc.msg}"
        return report

    lines = source.splitlines()

    # ---------- importها ----------
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if not node.module.startswith("aiobale"):
                continue

            line_no = _line_of(source, node)
            names = [alias.name for alias in node.names]
            mapped = [IMPORT_MAP.get(name, name) for name in names]

            unmapped = [n for n in names if n not in IMPORT_MAP]
            if unmapped:
                for name in unmapped:
                    report.unsupported.append(
                        Change(
                            line=line_no,
                            kind="unsupported",
                            before=name,
                            note=(
                                "در BADKING معادل مستقیم ندارد — تبدیل نشد؛ "
                                "دستی بررسی کن (API خیالی ساخته نمیشود)"
                            ),
                        )
                    )

            report.changes.append(
                Change(
                    line=line_no,
                    kind="import",
                    before=f"from {node.module} import {', '.join(names)}",
                    after=f"from badking import {', '.join(mapped)}",
                )
            )

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("aiobale"):
                    line_no = _line_of(source, node)
                    report.changes.append(
                        Change(
                            line=line_no,
                            kind="import",
                            before=f"import {alias.name}",
                            after="import badking",
                        )
                    )

    # ---------- متدهای ناسازگار ----------
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func

        name = ""
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id

        if not name:
            continue

        line_no = _line_of(source, node)

        if name in UNSUPPORTED:
            report.unsupported.append(
                Change(
                    line=line_no,
                    kind="unsupported",
                    before=name,
                    note=UNSUPPORTED[name],
                )
            )
        elif name in METHOD_MAP and METHOD_MAP[name] != name:
            report.changes.append(
                Change(
                    line=line_no,
                    kind="method",
                    before=f".{name}(",
                    after=f".{METHOD_MAP[name]}(",
                )
            )

    # ---------- الگوهای متنی ----------
    # AST همه چیز را نمی‌گیرد: مثلاً رشته‌های داخل کد
    text_patterns = [
        (r"\baiobale\b", "badking", "نام پکیج در متن"),
        (r"from aiobale\.", "from badking.", "import با زیرماژول"),
    ]

    for pattern, replacement, note in text_patterns:
        for match in re.finditer(pattern, source):
            line_no = source[: match.start()].count("\n") + 1
            # اگر قبلاً در changes هست، دوباره اضافه نکن
            if any(c.line == line_no and c.kind == "import" for c in report.changes):
                continue
            report.warnings.append(
                Change(
                    line=line_no,
                    kind="warning",
                    before=match.group(0),
                    note=note,
                )
            )

    return report


def migrate_source(source: str, path: str = "<string>") -> MigrationReport:
    """متن را تبدیل می‌کند و نتیجه را در `report.migrated` می‌گذارد."""
    report = analyze(source, path)
    if not report.ok:
        return report

    result = source

    # نام‌هایی که import شده‌اند — قبل از تبدیل import جمع می‌کنیم،
    # چون بعد از تبدیل دیگر قابل استخراج نیستند.
    imported_names: list[str] = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("aiobale"):
                imported_names.extend(alias.name for alias in node.names)
    except SyntaxError:
        pass

    # importها — نامهای unsupported حذف و به هشدار تبدیل میشوند تا
    # import خیالی (`from badking import Command`) ساخته نشود.
    unsupported_names = {c.before for c in report.unsupported}
    import_warnings: list[str] = []

    def _rewrite_import(m):
        original_names = [p.strip() for p in m.group(1).split(",")]
        kept = []
        dropped = []
        for name in original_names:
            base = name.split(" as ")[0].strip()
            if base in unsupported_names:
                dropped.append(name)
            else:
                kept.append(name)
        line = f"from badking import {_map_import_list(', '.join(kept))}" if kept else ""
        if dropped:
            line += "  # migration: Unsupported: " + ", ".join(dropped) + " (دستی بررسی کن)"
            import_warnings.extend(dropped)
        return line

    result = re.sub(
        r"from\s+aiobale(?:\.\w+)*\s+import\s+([^\n]+)",
        _rewrite_import,
        result,
    )
    result = re.sub(r"^import\s+aiobale\s*$", "import badking", result, flags=re.MULTILINE)
    result = re.sub(r"^import\s+aiobale\.(\w+)", r"import badking", result, flags=re.MULTILINE)

    # اسم‌های import‌شده در بدنه — وگرنه NameError می‌دهد
    result, renamed = _rename_bare_calls(result, imported_names)
    for item in renamed:
        report.changes.append(
            Change(line=0, kind="name", before=item.split(" → ")[0], after=item.split(" → ")[1])
        )

    # متدها — فقط آن‌هایی که مطمئنیم
    for old, new in METHOD_MAP.items():
        if old == new:
            continue
        result = re.sub(rf"\.{re.escape(old)}\(", f".{new}(", result)

    report.migrated = result
    return report


def _map_import_list(names: str) -> str:
    """'Client, F, Router' → 'Bot, F, Router'

    نام ناشناخته **تبدیل نمیشود** تا import خیالی ساخته نشود. چنین نامی
    توسط `analyze()` به عنوان unsupported گزارش میشود.
    """
    parts = [p.strip() for p in names.split(",")]
    mapped = []
    for part in parts:
        # alias را نگه دار: "Client as C"
        if " as " in part:
            original, alias = part.split(" as ", 1)
            original = original.strip()
            if original not in IMPORT_MAP:
                # import خیالی نسازیم — نام اصلی را نگه میداریم تا کاربر ببیند
                mapped.append(f"{original} as {alias.strip()}")
            else:
                mapped.append(f"{IMPORT_MAP[original]} as {alias.strip()}")
        else:
            # ناشناخته → همان نام (بدون ساخت API خیالی)
            mapped.append(IMPORT_MAP.get(part, part))
    return ", ".join(mapped)


def _rename_bare_calls(source: str, names: list[str]) -> tuple[str, list[str]]:
    """اسم‌هایی که import شده‌اند و در بدنه صدا زده می‌شوند را عوض می‌کند.

    اگر `from aiobale import Client` را به `from badking import Bot` تبدیل
    کنیم ولی `Client(...)` در بدنه بماند، فایل NameError می‌دهد. این
    تابع آن را می‌گیرد.

    Returns:
        (متن جدید، فهرست نام‌هایی که عوض شدند)
    """
    renamed = []

    for name in names:
        target = IMPORT_MAP.get(name)
        if not target or target == name:
            continue

        # فقط به عنوان اسم مستقل، نه بخشی از اسم بلندتر و نه بعد از نقطه
        pattern = rf"(?<![\w.]){re.escape(name)}(?![\w])"
        new_source, count = re.subn(pattern, target, source)

        if count:
            source = new_source
            renamed.append(f"{name} → {target}")

    return source, renamed


def migrate_file(
    path: str | Path,
    *,
    dry_run: bool = False,
    backup: bool = True,
) -> MigrationReport:
    """یک فایل را مهاجرت می‌دهد.

    Args:
        path: مسیر فایل.
        dry_run: اگر True، چیزی نوشته نمی‌شود.
        backup: اگر True، نسخه قبلی با پسوند ``.bak`` نگه داشته می‌شود.
    """
    path = Path(path)

    if not path.is_file():
        return MigrationReport(
            path=str(path),
            ok=False,
            error="فایل نیست",
        )

    try:
        # utf-8-sig: فایل‌های ویندوزی اغلب BOM دارند. بدون این، BOM به
        # عنوان کاراکتر نامرئی در خط اول می‌ماند و ast خطای نحوی می‌دهد.
        source = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return MigrationReport(
            path=str(path),
            ok=False,
            error="فایل UTF-8 نیست — دستی تبدیل کن",
        )

    report = migrate_source(source, str(path))

    if not report.ok or dry_run or not report.changes:
        return report

    if backup:
        path.with_suffix(path.suffix + ".bak").write_text(source, encoding="utf-8")

    # Path.write_text فقط از پایتون ۳.۱۰ آرگومان newline می‌گیرد.
    # با open می‌نویسیم تا ۳.۹ هم کار کند.
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(report.migrated)
    log.info("مهاجرت شد: %s (%d تغییر)", path, report.total)
    return report


def migrate_directory(
    root: str | Path,
    *,
    dry_run: bool = False,
    backup: bool = True,
    pattern: str = "*.py",
) -> list[MigrationReport]:
    """همه فایل‌های یک پوشه را مهاجرت می‌دهد."""
    root = Path(root)
    if not root.is_dir():
        raise MigrationError(f"پوشه نیست: {root}", hint="مسیر را چک کن.")

    reports = []
    for path in sorted(root.rglob(pattern)):
        if any(part in {".git", "__pycache__", ".venv", "venv"} for part in path.parts):
            continue
        reports.append(migrate_file(path, dry_run=dry_run, backup=backup))

    return reports


def migration_summary(reports: list[MigrationReport]) -> str:
    """خلاصه همه فایل‌ها."""
    if not reports:
        return "فایلی پیدا نشد."

    changed = [r for r in reports if r.changes]
    manual = [r for r in reports if r.needs_manual_work]
    failed = [r for r in reports if not r.ok]

    lines = [
        f"{len(reports)} فایل بررسی شد",
        f"  {len(changed)} فایل تغییر کرد",
        f"  {len(manual)} فایل نیاز به کار دستی دارد",
        f"  {len(failed)} فایل خطا داشت",
    ]

    if manual:
        lines.append("")
        lines.append("نیاز به کار دستی:")
        for report in manual:
            lines.append(f"  {report.path}")
            for item in report.unsupported[:3]:
                lines.append(f"      {item}")

    return "\n".join(lines)


__all__ = [
    "Application",
    "BaleMethod",
    "Bot",
    "Dispatcher",
    "F",
    "Change",
    "IMPORT_MAP",
    "METHOD_MAP",
    "MigrationError",
    "MigrationReport",
    "UNSUPPORTED",
    "analyze",
    "migrate_directory",
    "migrate_file",
    "migrate_source",
    "migration_summary",
]


# ---------- لایه سازگاری با سبک python-telegram-bot ----------

# این‌ها را از هسته دوباره صادر می‌کنیم تا کسی که از کتابخانه دیگری
# می‌آید، بتواند از مسیر آشنا import کند.
from ..core.bot import Bot  # noqa: E402
from ..core.dispatcher import Dispatcher  # noqa: E402
from ..filters.magic import F  # noqa: E402


class Application:
    """سبک ``Application.builder().token(...).build()``.

        app = Application.builder().token("123:ABC").build()
        app.bot        # نمونه Bot
        app.dispatcher # نمونه Dispatcher

    چرا: بعضی‌ها از کتابخانه‌های دیگر می‌آیند و این الگو را می‌شناسند. یک
    راه آشنا، مهاجرت را آسان‌تر می‌کند.
    """

    def __init__(self, bot: Any, dispatcher: Any = None) -> None:
        self.bot = bot
        self.dispatcher = dispatcher

    @classmethod
    def builder(cls) -> "ApplicationBuilder":
        """شروع ساخت."""
        return ApplicationBuilder()

    def __repr__(self) -> str:
        return f"<Application bot={self.bot!r}>"


class ApplicationBuilder:
    """سازنده گام‌به‌گام."""

    def __init__(self) -> None:
        self._token = ""
        self._dispatcher: Any = None

    def token(self, token: str) -> "ApplicationBuilder":
        """توکن ربات."""
        self._token = token
        return self

    def dispatcher(self, dispatcher: Any) -> "ApplicationBuilder":
        """دیسپچر دلخواه."""
        self._dispatcher = dispatcher
        return self

    def build(self) -> Application:
        """می‌سازد."""
        from ..core.bot import Bot
        from ..core.dispatcher import Dispatcher

        if not self._token:
            raise MigrationError(
                "توکن تنظیم نشده",
                hint="Application.builder().token('123:ABC').build()",
            )

        bot = Bot(self._token)
        dispatcher = self._dispatcher or Dispatcher()
        return Application(bot, dispatcher)
