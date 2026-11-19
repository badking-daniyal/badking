"""تست نمونه‌ها: هر فایل در examples/ باید سالم باشد.

نمونه‌های شکسته بدترین نوع مستندات‌اند. این تست مطمئن می‌شود هر نمونه
حداقل از نظر نحوی درست است و چیزی import می‌کند که وجود ندارد.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
PY_FILES = sorted(p for p in EXAMPLES.glob("*.py") if p.name != "__init__.py")


def test_examples_exist():
    assert len(PY_FILES) >= 20, f"فقط {len(PY_FILES)} نمونه هست"


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: p.name)
def test_syntax(path: Path):
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: p.name)
def test_has_docstring(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    doc = ast.get_docstring(tree)
    assert doc, f"{path.name} docstring ندارد"
    assert len(doc) > 30, f"{path.name} docstring خیلی کوتاه است"


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: p.name)
def test_badking_imports_exist(path: Path):
    """هر چیزی که از badking import می‌شود باید واقعاً وجود داشته باشد."""
    import badking

    tree = ast.parse(path.read_text(encoding="utf-8"))
    missing = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "badking":
            for alias in node.names:
                if not hasattr(badking, alias.name):
                    missing.append(alias.name)

    assert missing == [], f"{path.name} از badking چیز ناموجود import می‌کند: {missing}"


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: p.name)
def test_no_hardcoded_token(path: Path):
    """توکن واقعی نباید در نمونه باشد."""
    import re

    source = path.read_text(encoding="utf-8")
    # الگوی توکن: ۸ تا ۱۲ رقم، دو نقطه، ۳۰+ کاراکتر
    matches = re.findall(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", source)
    assert matches == [], f"{path.name} توکن واقعی دارد"


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: p.name)
def test_has_main_guard(path: Path):
    """هر نمونه باید قابل اجرا باشد."""
    source = path.read_text(encoding="utf-8")
    assert '__name__ == "__main__"' in source, f"{path.name} نقطه ورود ندارد"


def test_examples_are_numbered():
    """شماره‌گذاری پیوسته باشد."""
    numbers = []
    for path in PY_FILES:
        prefix = path.name.split("_")[0]
        assert prefix.isdigit(), f"{path.name} شماره ندارد"
        numbers.append(int(prefix))

    assert numbers == sorted(numbers), "نمونه‌ها به ترتیب شماره نیستند"
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"شماره‌ها پیوسته نیستند: {numbers}"
    )


def test_examples_readme_lists_examples():
    """examples/README.md باید همه نمونه‌ها را فهرست کند."""
    readme = EXAMPLES / "README.md"
    assert readme.is_file(), "examples/README.md نیست"

    text = readme.read_text(encoding="utf-8")
    missing = [path.name for path in PY_FILES if path.name not in text]
    assert missing == [], f"در examples/README.md فهرست نشده‌اند: {missing}"


def test_root_readme_links_examples():
    """README اصلی باید به پوشه نمونه‌ها اشاره کند."""
    readme = (EXAMPLES.parent / "README.md").read_text(encoding="utf-8")
    assert "examples" in readme, "README اصلی به examples اشاره نمی‌کند"
