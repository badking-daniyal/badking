"""Migration behavioral validation — اجرای واقعی پروژه تبدیلشده (نه فقط import).

این تستها ثابت میکنند که کد تبدیلشده aiobale → BADKING واقعاً کار میکند:
Router ساخته میشود، کیبورد با دکمه و callback درست است، و متد answer→reply تبدیل میشود.
"""

from __future__ import annotations

from badking.compat import analyze, migrate_source

SAMPLE = '''\
"""نمونه ربات aiobale."""
from aiobale import Client, Router, F
from aiobale.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_app():
    router = Router()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="تایید", callback_data="ok")]]
    )
    return router, keyboard


async def handle(client, message):
    await message.answer("سلام")
    return True
'''


class TestMigrationBehavioral:
    def test_analyze_detects_all_changes(self):
        report = analyze(SAMPLE, "sample_bot.py")
        assert len(report.changes) == 3
        kinds = {c.kind for c in report.changes}
        assert "import" in kinds
        assert "method" in kinds
        assert report.unsupported == []

    def test_migrated_code_compiles(self):
        report = migrate_source(SAMPLE, "sample_bot.py")
        compile(report.migrated, "sample_bot.py", "exec")

    def test_migrated_code_executes_and_builds_objects(self):
        report = migrate_source(SAMPLE, "sample_bot.py")
        ns = {}
        exec(compile(report.migrated, "sample_bot.py", "exec"), ns)

        router, keyboard = ns["build_app"]()
        assert type(router).__name__ == "Router"
        assert type(keyboard).__name__ == "InlineKeyboardMarkup"
        assert len(keyboard.inline_keyboard) == 1
        assert keyboard.inline_keyboard[0][0].text == "تایید"
        assert keyboard.inline_keyboard[0][0].callback_data == "ok"

    def test_answer_becomes_reply(self):
        report = migrate_source(SAMPLE, "sample_bot.py")
        assert "message.reply(" in report.migrated
        assert "message.answer(" not in report.migrated

    def test_unsupported_import_does_not_create_fake_api(self):
        """Command معادل مستقیم ندارد — نباید from badking import Command ساخت."""
        report = migrate_source("from aiobale.filters import Command\n")
        assert "from badking import Command" not in report.migrated
        assert any(c.before == "Command" for c in report.unsupported)
        assert "Unsupported" in report.migrated
