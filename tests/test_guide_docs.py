"""تست ۳۹ صفحه مستندات guide.

سند مأموریت میخواهد: هر قابلیت صفحه مستقل با API، پارامترها، خروجی،
Exception، مثال اجرایی و محدودیت بله.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import badking

GUIDE = Path(__file__).resolve().parents[1] / "docs" / "guide"


def test_all_39_pages_exist():
    pages = sorted(p for p in GUIDE.glob("*.md") if p.name != "README.md")
    assert len(pages) == 39, f"تعداد صفحات {len(pages)} است، ۳۹ انتظار میرود"
    for n in range(1, 40):
        matches = [p for p in pages if p.name.startswith(f"{n:02d}-")]
        assert matches, f"صفحه {n:02d} وجود ندارد"


def test_every_page_has_content():
    for page in GUIDE.glob("*.md"):
        if page.name == "README.md":
            continue
        text = page.read_text(encoding="utf-8")
        assert len(text) > 60, f"{page.name} خیلی کوتاه است"
        assert text.startswith("# "), f"{page.name} عنوان ندارد"


def test_code_blocks_compile():
    """تمام مثالهای پایتون کامپایل شوند."""
    for page in GUIDE.glob("*.md"):
        text = page.read_text(encoding="utf-8")
        for block in re.findall(r"```python\n(.*?)```", text, re.DOTALL):
            try:
                ast.parse(block)
            except SyntaxError as exc:
                raise AssertionError(f"{page.name}: مثال کامپایل نشد: {exc}")


def test_documented_bot_methods_exist():
    """جدول متدهای Bot در صفحه 05 فقط متدهای واقعی را نشان دهد."""
    page = GUIDE / "05-bot-api.md"
    text = page.read_text(encoding="utf-8")
    for match in re.finditer(r"\|\s*`(\w+)`\s*\|", text):
        name = match.group(1)
        assert hasattr(badking.Bot, name), f"Bot.{name} وجود ندارد"


def test_documented_self_methods_exist():
    from badking.hybrid import SelfBot

    page = GUIDE / "06-self-client.md"
    text = page.read_text(encoding="utf-8")
    for match in re.finditer(r"\|\s*`(\w+)`\s*\|", text):
        name = match.group(1)
        assert hasattr(SelfBot, name), f"SelfBot.{name} وجود ندارد"


def test_all_imports_exist():
    """هر import badking در صفحات باید واقعی باشد."""
    for page in GUIDE.glob("*.md"):
        text = page.read_text(encoding="utf-8")
        for match in re.finditer(r"from badking(?:\.[\w.]+)? import ([^\n]+)", text):
            for name in [n.strip() for n in match.group(1).split(",")]:
                if not name:
                    continue
                assert hasattr(badking, name), f"{page.name}: badking.{name} وجود ندارد"


def test_blocked_items_labelled():
    """صفحات مربوط به موارد تأییدنشده باید صریحاً BLOCKED بگویند."""
    for name in ("06-self-client.md", "09-rpc-reference.md", "07-authentication.md"):
        text = (GUIDE / name).read_text(encoding="utf-8")
        assert "BLOCKED" in text, f"{name} وضعیت BLOCKED را ذکر نکرده"


def test_no_fake_performance_claim():
    text = (GUIDE / "32-performance.md").read_text(encoding="utf-8")
    assert "No comparison with aiobale has been measured" in text


def test_guide_index_exists():
    """یک فایل نمایه برایNavigation لازم است."""
    index = GUIDE / "README.md"
    assert index.is_file()
    text = index.read_text(encoding="utf-8")
    for n in range(1, 40):
        assert f"{n:02d}-" in text, f"صفحه {n:02d} در نمایه نیست"
