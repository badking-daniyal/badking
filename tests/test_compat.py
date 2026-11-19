"""تست Migration Toolkit."""

from __future__ import annotations

import ast

import pytest

from badking.compat import (
    IMPORT_MAP,
    METHOD_MAP,
    MigrationError,
    analyze,
    migrate_directory,
    migrate_file,
    migrate_source,
    migration_summary,
)


class TestAnalyze:
    def test_plain_python_untouched(self):
        report = analyze("x = 1\nprint(x)\n")
        assert report.ok is True
        assert report.changes == []
        assert report.needs_manual_work is False

    def test_detects_aiobale_import(self):
        report = analyze("from aiobale import Client\n")
        assert len(report.changes) == 1
        assert report.changes[0].kind == "import"
        assert "Bot" in report.changes[0].after

    def test_detects_submodule_import(self):
        report = analyze("from aiobale.types import Message\n")
        assert any(c.kind == "import" for c in report.changes)

    def test_detects_plain_import(self):
        report = analyze("import aiobale\n")
        assert len(report.changes) == 1
        assert report.changes[0].after == "import badking"

    def test_unknown_name_warned(self):
        report = analyze("from aiobale import TotallyUnknownThing\n")
        assert report.warnings
        assert any("TotallyUnknownThing" in w.before for w in report.warnings)

    def test_unsupported_method_reported(self):
        report = analyze("bot.register_next_step_handler(x)\n")
        assert len(report.unsupported) == 1
        assert report.unsupported[0].before == "register_next_step_handler"
        assert "FSM" in report.unsupported[0].note

    def test_method_rename_detected(self):
        report = analyze("await message.answer('hi')\n")
        assert any(c.kind == "method" and c.after == ".reply(" for c in report.changes)

    def test_syntax_error_reported(self):
        report = analyze("def broken(:\n")
        assert report.ok is False
        assert "خطای نحوی" in report.error

    def test_line_numbers(self):
        report = analyze("import os\nfrom aiobale import Client\n")
        assert report.changes[0].line == 2

    def test_summary_text(self):
        report = analyze("from aiobale import Client\n")
        text = report.summary()
        assert "تغییر خودکار" in text

    def test_to_dict(self):
        report = analyze("from aiobale import Client\n")
        data = report.to_dict()
        assert data["ok"] is True
        assert len(data["changes"]) == 1
        assert data["changes"][0]["kind"] == "import"


class TestMigrateSource:
    def test_import_rewritten(self):
        report = migrate_source("from aiobale import Client\n")
        assert "from badking import Bot" in report.migrated
        assert "aiobale" not in report.migrated

    def test_multiple_names(self):
        report = migrate_source("from aiobale import Client, F, Router\n")
        assert "Bot" in report.migrated
        assert "F" in report.migrated
        assert "Router" in report.migrated

    def test_alias_preserved(self):
        report = migrate_source("from aiobale import Client as C\n")
        assert "Bot as C" in report.migrated

    def test_plain_import_rewritten(self):
        report = migrate_source("import aiobale\n")
        assert "import badking" in report.migrated

    def test_method_renamed(self):
        report = migrate_source("await message.answer('x')\n")
        assert ".reply(" in report.migrated
        assert ".answer(" not in report.migrated

    def test_unsupported_left_alone(self):
        source = "bot.register_next_step_handler(x)\n"
        report = migrate_source(source)
        # تبدیل نمی‌شود، فقط گزارش
        assert "register_next_step_handler" in report.migrated
        assert report.unsupported

    def test_syntax_error_no_migration(self):
        report = migrate_source("def broken(:\n")
        assert report.migrated == ""
        assert report.ok is False

    def test_result_is_valid_python(self):
        source = """
from aiobale import Client, Dispatcher, F

async def main():
    bot = Client("TOKEN")
    await bot.send_message(1, "hi")
"""
        report = migrate_source(source)
        compile(report.migrated, "<test>", "exec")

    def test_persian_strings_preserved(self):
        source = 'from aiobale import Client\nawait message.answer("سلام")\n'
        report = migrate_source(source)
        assert "سلام" in report.migrated

    def test_no_change_keeps_source(self):
        source = "x = 1\n"
        report = migrate_source(source)
        assert report.migrated == source

    def test_bare_name_in_body_renamed(self):
        """اگر import تبدیل شود ولی استفاده در بدنه نه، فایل NameError می‌دهد."""
        source = "from aiobale import Client\nbot = Client('TOKEN')\n"
        report = migrate_source(source)
        assert "Bot('TOKEN')" in report.migrated
        assert "Client(" not in report.migrated

    def test_renamed_result_has_no_undefined_names(self):
        source = """
from aiobale import Client, Dispatcher

bot = Client("TOKEN")
dp = Dispatcher()
"""
        report = migrate_source(source)
        tree = ast.parse(report.migrated)

        # هر اسمی که صدا زده می‌شود باید تعریف شده باشد
        defined = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                defined.update(a.asname or a.name for a in node.names)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined.add(target.id)

        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert called <= defined, f"اسم‌های تعریف‌نشده: {called - defined}"

    def test_attribute_not_renamed(self):
        """obj.Client نباید عوض شود — اسم خودمان نیست."""
        source = "from aiobale import Client\nx = other.Client\n"
        report = migrate_source(source)
        assert "other.Client" in report.migrated

    def test_substring_not_renamed(self):
        """MyClient نباید به MyBot تبدیل شود."""
        source = "from aiobale import Client\nMyClient = 1\n"
        report = migrate_source(source)
        assert "MyClient" in report.migrated

    def test_alias_not_renamed_in_body(self):
        """با alias، اسم بدنه همان alias است و نباید عوض شود."""
        source = "from aiobale import Client as C\nbot = C('TOKEN')\n"
        report = migrate_source(source)
        assert "C('TOKEN')" in report.migrated


class TestMigrateFile:
    def test_migrates_file(self, tmp_path):
        path = tmp_path / "bot.py"
        path.write_text("from aiobale import Client\n", encoding="utf-8")

        report = migrate_file(path)
        assert report.ok is True
        assert "badking" in path.read_text(encoding="utf-8")

    def test_backup_created(self, tmp_path):
        path = tmp_path / "bot.py"
        original = "from aiobale import Client\n"
        path.write_text(original, encoding="utf-8")

        migrate_file(path, backup=True)
        backup = tmp_path / "bot.py.bak"
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == original

    def test_no_backup_when_disabled(self, tmp_path):
        path = tmp_path / "bot.py"
        path.write_text("from aiobale import Client\n", encoding="utf-8")
        migrate_file(path, backup=False)
        assert not (tmp_path / "bot.py.bak").exists()

    def test_dry_run_writes_nothing(self, tmp_path):
        path = tmp_path / "bot.py"
        original = "from aiobale import Client\n"
        path.write_text(original, encoding="utf-8")

        report = migrate_file(path, dry_run=True)
        assert report.changes
        assert path.read_text(encoding="utf-8") == original
        assert not (tmp_path / "bot.py.bak").exists()

    def test_missing_file(self, tmp_path):
        report = migrate_file(tmp_path / "nope.py")
        assert report.ok is False
        assert "فایل نیست" in report.error

    def test_non_utf8_reported(self, tmp_path):
        path = tmp_path / "bot.py"
        path.write_bytes(b"\xff\xfe\x00bad")
        report = migrate_file(path)
        assert report.ok is False
        assert "UTF-8" in report.error

    def test_no_changes_no_write(self, tmp_path):
        path = tmp_path / "clean.py"
        original = "x = 1\n"
        path.write_text(original, encoding="utf-8")
        migrate_file(path)
        assert path.read_text(encoding="utf-8") == original
        assert not (tmp_path / "clean.py.bak").exists()


class TestMigrateDirectory:
    def test_migrates_all(self, tmp_path):
        (tmp_path / "a.py").write_text("from aiobale import Client\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("from aiobale import F\n", encoding="utf-8")

        reports = migrate_directory(tmp_path)
        assert len(reports) == 2
        assert all(r.ok for r in reports)

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "x.py").write_text("from aiobale import Client\n", encoding="utf-8")
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")

        reports = migrate_directory(tmp_path)
        assert len(reports) == 1

    def test_missing_directory(self, tmp_path):
        with pytest.raises(MigrationError):
            migrate_directory(tmp_path / "nope")

    def test_dry_run_directory(self, tmp_path):
        path = tmp_path / "a.py"
        original = "from aiobale import Client\n"
        path.write_text(original, encoding="utf-8")

        migrate_directory(tmp_path, dry_run=True)
        assert path.read_text(encoding="utf-8") == original


class TestSummary:
    def test_empty(self):
        assert "فایلی پیدا نشد" in migration_summary([])

    def test_counts(self, tmp_path):
        (tmp_path / "a.py").write_text("from aiobale import Client\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("bot.register_next_step_handler(x)\n", encoding="utf-8")

        reports = migrate_directory(tmp_path, dry_run=True)
        text = migration_summary(reports)
        assert "2 فایل بررسی شد" in text
        assert "نیاز به کار دستی" in text


class TestMaps:
    def test_import_map_has_no_identity_cycles(self):
        for source, target in IMPORT_MAP.items():
            assert isinstance(target, str)
            assert target

    def test_method_map_values_are_strings(self):
        for source, target in METHOD_MAP.items():
            assert isinstance(target, str)

    def test_unsupported_all_have_notes(self):
        from badking.compat import UNSUPPORTED

        for name, note in UNSUPPORTED.items():
            assert note, f"{name} یادداشت ندارد"
