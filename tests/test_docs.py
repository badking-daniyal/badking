"""تست مستندات: فارسی و انگلیسی باید هم‌تراز بمانند.

مستنداتی که فقط یک زبانش به‌روز می‌شود، بدتر از نداشتن مستندات است.
این تست بخش‌های اصلی را در هر دو می‌سنجد.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "docs"
EN = DOCS / "en" / "README.md"
FA = DOCS / "fa" / "README.md"


def headings(path: Path) -> list[str]:
    """عنوان‌های سطح ۲ (##) را برمی‌گرداند."""
    text = path.read_text(encoding="utf-8")
    return [line.lstrip("#").strip() for line in text.splitlines() if line.startswith("## ")]


def code_blocks(path: Path) -> list[str]:
    """محتوای بلوک‌های کد."""
    text = path.read_text(encoding="utf-8")
    return re.findall(r"```[a-z]*\n(.*?)```", text, re.DOTALL)


def test_both_exist():
    assert EN.is_file(), "docs/en/README.md نیست"
    assert FA.is_file(), "docs/fa/README.md نیست"


def test_same_number_of_sections():
    en, fa = headings(EN), headings(FA)
    assert len(en) == len(fa), (
        f"تعداد بخش‌ها یکی نیست: en={len(en)} fa={len(fa)}\n"
        f"en: {en}\nfa: {fa}"
    )


def test_same_code_block_count():
    en, fa = code_blocks(EN), code_blocks(FA)
    assert len(en) == len(fa), (
        f"تعداد بلوک کد یکی نیست: en={len(en)} fa={len(fa)}"
    )


def _shape(block: str) -> str:
    """شکل کد را برمی‌گرداند، بدون کامنت و بدون محتوای رشته.

    کامنت و متن پیام باید ترجمه شوند. آنچه نباید فرق کند ساختار است:
    همان فراخوانی‌ها، همان ترتیب، همان اسم‌ها.
    """
    import ast

    body = "\n".join(f"    {line}" for line in block.splitlines())
    tree = ast.parse(f"async def _doc_example():\n{body}\n")

    for node in ast.walk(tree):
        # محتوای رشته را خالی کن — ترجمه مجاز است
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = "<str>"

    return ast.dump(tree, annotate_fields=False)


def test_python_blocks_have_same_structure():
    """کد پایتون در دو زبان باید یک ساختار داشته باشد.

    کامنت و متن پیام ترجمه می‌شود؛ فراخوانی‌ها نه.
    """
    en = [b for b in code_blocks(EN) if "from badking" in b or "await " in b]
    fa = [b for b in code_blocks(FA) if "from badking" in b or "await " in b]

    assert len(en) == len(fa), f"تعداد بلوک پایتون یکی نیست: en={len(en)} fa={len(fa)}"
    for index, (a, b) in enumerate(zip(en, fa)):
        assert _shape(a) == _shape(b), (
            f"ساختار بلوک پایتون شماره {index + 1} یکی نیست:\nEN:\n{a}\nFA:\n{b}"
        )


def test_python_blocks_compile():
    """هر نمونه پایتون در مستندات باید کامپایل شود.

    نمونه‌ها تکه‌اند، نه فایل کامل — بعضی `await` در سطح ماژول دارند.
    پس در یک تابع async می‌پیچیم تا همان چیزی سنجیده شود که کاربر
    کپی می‌کند.
    """
    for path in (EN, FA):
        for block in code_blocks(path):
            if "from badking" not in block and "await " not in block:
                continue

            body = "\n".join(f"    {line}" for line in block.splitlines())
            wrapped = f"async def _doc_example():\n{body}\n"

            try:
                compile(wrapped, str(path), "exec")
            except SyntaxError as exc:
                pytest.fail(f"{path.name}: کد مستندات کامپایل نمی‌شود: {exc}\n{block}")


def test_badking_imports_in_docs_exist():
    """هر چیزی که در مستندات import می‌شود باید واقعاً باشد."""
    import badking

    for path in (EN, FA):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"from badking import ([^\n]+)", text):
            names = [n.strip() for n in match.group(1).split(",")]
            for name in names:
                if not name or name.startswith("#"):
                    continue
                assert hasattr(badking, name), (
                    f"{path.name}: badking.{name} وجود ندارد"
                )


def test_no_placeholder_text():
    """جای‌نگهدار رهاشده نباشد."""
    for path in (EN, FA):
        text = path.read_text(encoding="utf-8")
        for marker in ("TODO", "TBD", "FIXME", "XXX", "{{", "}}"):
            assert marker not in text, f"{path.name} شامل {marker} است"


def test_persian_doc_has_persian():
    text = FA.read_text(encoding="utf-8")
    persian = len(re.findall(r"[\u0600-\u06FF]", text))
    assert persian > 1000, f"متن فارسی کم است: {persian} کاراکتر"


def test_english_doc_has_no_persian_prose():
    """متن انگلیسی نباید فارسی قاطی داشته باشد (به جز نام‌ها)."""
    text = EN.read_text(encoding="utf-8")
    # فقط خطوطی که کد نیستند
    prose = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith(("```", "|"))
    )
    persian_words = re.findall(r"[\u0600-\u06FF]{4,}", prose)
    # «بله» به عنوان نام محصول مجاز است
    unexpected = [w for w in persian_words if w != "بله"]
    assert unexpected == [], f"کلمه فارسی در متن انگلیسی: {unexpected[:5]}"


def test_install_command_present_in_both():
    for path in (EN, FA):
        text = path.read_text(encoding="utf-8")
        assert "pip install badking" in text, f"{path.name} دستور نصب ندارد"


def test_cli_commands_documented_match_real():
    """دستورهایی که در مستندات هست باید در CLI واقعی باشند."""
    from badking.cli.main import build_parser

    parser = build_parser()
    real = set()
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            real.update(action.choices)

    text = EN.read_text(encoding="utf-8")
    documented = set(re.findall(r"^badking (\w+)", text, re.MULTILINE))

    unknown = documented - real
    assert unknown == set(), f"در مستندات هست ولی در CLI نیست: {unknown}"


def test_cli_commands_in_persian_doc_too():
    """همان دستورها در نسخه فارسی هم باشد."""
    from badking.cli.main import build_parser

    parser = build_parser()
    real = set()
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            real.update(action.choices)

    text = FA.read_text(encoding="utf-8")
    documented = set(re.findall(r"^badking (\w+)", text, re.MULTILINE))

    unknown = documented - real
    assert unknown == set(), f"در مستندات فارسی هست ولی در CLI نیست: {unknown}"


def test_parser_has_migrate_command():
    """دستور migrate باید واقعاً وجود داشته باشد."""
    from badking.cli.main import build_parser

    parser = build_parser()
    real = set()
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            real.update(action.choices)

    assert "migrate" in real
    assert "doctor" in real
    assert "rpc" in real


def test_docs_linked_from_root_readme():
    readme = (DOCS.parent / "README.md").read_text(encoding="utf-8")
    assert "docs/" in readme or "docs.badking.ir" in readme, (
        "README اصلی به مستندات اشاره نمی‌کند"
    )
