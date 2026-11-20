"""دستورهای عیب‌یابی CLI: doctor، info، check، test.

فلسفه: کاربر نباید برای فهمیدن «چرا کار نمی‌کند» سه ساعت لاگ بخواند.
`badking doctor` همه چیز را می‌سنجد و می‌گوید کدام درست است، کدام نیست،
و برای هر مورد نادرست دقیقاً چه کار کند.
"""

from __future__ import annotations

import importlib
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------- رنگ ----------

_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    return os.name != "nt" or "WT_SESSION" in os.environ or "ANSICON" in os.environ


_COLOR = _supports_color()


def _c(text: str, color: str) -> str:
    return f"{color}{text}{_RESET}" if _COLOR else text


def ok(label: str, detail: str = "") -> str:
    mark = _c("✓", _GREEN)
    return f"  {mark} {label}" + (f"  {_c(detail, _DIM)}" if detail else "")


def bad(label: str, detail: str = "") -> str:
    mark = _c("✗", _RED)
    return f"  {mark} {label}" + (f"  {_c(detail, _DIM)}" if detail else "")


def warn(label: str, detail: str = "") -> str:
    mark = _c("!", _YELLOW)
    return f"  {mark} {label}" + (f"  {_c(detail, _DIM)}" if detail else "")


# ---------- بررسی‌های تک‌تک ----------

def check_python() -> tuple[bool, str, str]:
    """نسخه پایتون باید ۳.۹ یا بالاتر باشد."""
    version = sys.version_info
    text = f"{version.major}.{version.minor}.{version.micro}"
    if version >= (3, 9):
        return True, text, ""
    return False, text, "پایتون ۳.۹ یا بالاتر لازم است. python.org را ببین."


def check_import() -> tuple[bool, str, str]:
    """خود بسته درست import می‌شود؟"""
    try:
        module = importlib.import_module("badking")
        return True, getattr(module, "__version__", "?"), ""
    except Exception as exc:  # noqa: BLE001
        return False, type(exc).__name__, f"import شکست خورد: {exc}"


def check_optional_deps() -> list[tuple[bool, str, str]]:
    """وابستگی‌های اختیاری: کدام نصب است، کدام نیست."""
    results = []
    optional = {
        "websockets": "لایه self-bot (اجباری برای Internal API)",
        "aiohttp": "سرور webhook",
        "pydantic": "اعتبارسنجی تایپ‌ها",
        "pillow": "پردازش تصویر",
    }
    for name, why in optional.items():
        try:
            importlib.import_module(name)
            results.append((True, name, why))
        except ImportError:
            results.append((False, name, why))
    return results


def check_network(host: str = "tapi.bale.ai", port: int = 443, timeout: float = 5.0) -> tuple[bool, str, str]:
    """اتصال TCP به سرور بله."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port}", ""
    except socket.gaierror:
        return False, f"{host}:{port}", "دامنه حل نشد. DNS یا VPN را بررسی کن."
    except socket.timeout:
        return False, f"{host}:{port}", "اتصال زمان‌بندی شد. فایروال یا فیلترینگ."
    except OSError as exc:
        return False, f"{host}:{port}", f"اتصال برقرار نشد: {exc}"


def check_token() -> tuple[bool, str, str]:
    """آیا توکنی در محیط هست؟"""
    for var in ("BADKING_TOKEN", "BALE_TOKEN", "BOT_TOKEN", "TELEGRAM_BOT_TOKEN"):
        value = os.environ.get(var)
        if value:
            # فقط ۴ کاراکتر آخر — نمایش ابتدای توکن (شامل شناسه ربات) نشان ندهیم.
            masked = "…" + value[-4:] if len(value) > 4 else "…"
            return True, f"{var}={masked}", ""
    return False, "پیدا نشد", "توکن را در .env بگذار: BADKING_TOKEN=123:ABC"


def check_env_file() -> tuple[bool, str, str]:
    """فایل .env در پوشه فعلی."""
    path = Path(".env")
    if path.is_file():
        return True, str(path.resolve()), ""
    return False, "نیست", "اختیاری. برای نگه‌داشتن توکن بیرون از کد."


def check_session_file() -> tuple[bool, str, str]:
    """فایل نشست self-bot."""
    candidates = list(Path(".").glob("*.session"))
    if candidates:
        path = candidates[0]
        size = path.stat().st_size
        return True, f"{path.name} ({size} بایت)", ""
    return False, "نیست", "برای self-bot لازم است: badking login --phone 0912..."


def check_write_permission() -> tuple[bool, str, str]:
    """آیا در پوشه فعلی می‌توان نوشت؟"""
    probe = Path(".badking_write_test")
    try:
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True, str(Path.cwd()), ""
    except OSError as exc:
        return False, str(Path.cwd()), f"نوشتن ممکن نیست: {exc}"


def check_git() -> tuple[bool, str, str]:
    """git نصب است؟ (برای deploy و نسخه‌بندی)"""
    exe = shutil.which("git")
    if not exe:
        return False, "نصب نیست", "اختیاری. git-scm.com"
    try:
        out = subprocess.run(
            [exe, "--version"], capture_output=True, text=True, timeout=5
        )
        return True, out.stdout.strip(), ""
    except (OSError, subprocess.SubprocessError):
        return False, exe, "git اجرا نشد."


def check_disk() -> tuple[bool, str, str]:
    """فضای دیسک."""
    try:
        usage = shutil.disk_usage(Path.cwd())
        free_gb = usage.free / (1024**3)
        if free_gb < 0.5:
            return False, f"{free_gb:.1f} GB آزاد", "فضای دیسک کم است."
        return True, f"{free_gb:.1f} GB آزاد", ""
    except OSError:
        return True, "?", ""


# ---------- doctor ----------

def run_doctor(*, network: bool = True, verbose: bool = False) -> int:
    """همه بررسی‌ها را اجرا می‌کند. ۰ یعنی سالم، ۱ یعنی مشکلی هست."""
    print()
    print(_c("BADKING doctor", _BOLD))
    print(_c("─" * 46, _DIM))

    problems = 0
    warnings = 0

    print(_c("\nمحیط", _BOLD))
    good, detail, hint = check_python()
    print(ok("پایتون", detail) if good else bad("پایتون", detail))
    if not good:
        problems += 1
        print(f"      {_c(hint, _YELLOW)}")

    print(ok("سیستم", f"{platform.system()} {platform.release()}"))
    print(ok("معماری", platform.machine()))

    print(_c("\nبسته", _BOLD))
    good, detail, hint = check_import()
    print(ok("badking", f"نسخه {detail}") if good else bad("badking", detail))
    if not good:
        problems += 1
        print(f"      {_c(hint, _YELLOW)}")

    print(_c("\nوابستگی‌های اختیاری", _BOLD))
    for good, name, why in check_optional_deps():
        if good:
            print(ok(name, why))
        else:
            print(warn(name, f"نصب نیست — {why}"))
            warnings += 1

    print(_c("\nپیکربندی", _BOLD))
    good, detail, hint = check_token()
    print(ok("توکن", detail) if good else warn("توکن", detail))
    if not good:
        warnings += 1
        if verbose:
            print(f"      {_c(hint, _DIM)}")

    good, detail, hint = check_env_file()
    print(ok(".env", detail) if good else warn(".env", detail))

    good, detail, hint = check_session_file()
    print(ok("نشست self-bot", detail) if good else warn("نشست self-bot", detail))

    print(_c("\nدسترسی", _BOLD))
    good, detail, hint = check_write_permission()
    print(ok("نوشتن در پوشه", detail) if good else bad("نوشتن در پوشه", detail))
    if not good:
        problems += 1
        print(f"      {_c(hint, _YELLOW)}")

    good, detail, hint = check_disk()
    print(ok("دیسک", detail) if good else warn("دیسک", detail))

    good, detail, hint = check_git()
    print(ok("git", detail) if good else warn("git", detail))

    if network:
        print(_c("\nشبکه", _BOLD))
        good, detail, hint = check_network()
        print(ok("سرور بله", detail) if good else bad("سرور بله", detail))
        if not good:
            problems += 1
            print(f"      {_c(hint, _YELLOW)}")

    print()
    print(_c("─" * 46, _DIM))
    if problems == 0 and warnings == 0:
        print(_c("  همه چیز سالم است.", _GREEN))
    elif problems == 0:
        print(_c(f"  آماده کار. {warnings} مورد اختیاری نصب نیست.", _GREEN))
    else:
        print(_c(f"  {problems} مشکل جدی، {warnings} هشدار.", _RED))
        print(_c("  موارد ✗ را برطرف کن؛ بقیه اختیاری‌اند.", _DIM))
    print()
    return 0 if problems == 0 else 1


# ---------- info ----------

def run_info() -> int:
    """خلاصه‌ای از نسخه، امکانات و محیط."""
    try:
        import badking
    except Exception as exc:  # noqa: BLE001
        print(bad("بسته import نشد", str(exc)))
        return 1

    print()
    print(f"{_c('BADKING', _BOLD)} {getattr(badking, '__version__', '?')}")
    print(_c("─" * 46, _DIM))
    print(f"  پایتون      {platform.python_version()}")
    print(f"  سیستم       {platform.system()} {platform.release()}")
    print(f"  صادرات      {len(getattr(badking, '__all__', []))}")
    print(f"  مسیر        {Path(badking.__file__).parent}")

    try:
        from badking.hybrid.rpc import registry

        print(f"  RPC         {len(registry.names())} متد")
    except Exception:  # noqa: BLE001
        print("  RPC         در دسترس نیست")

    print()
    print(_c("امکانات", _BOLD))
    features = [
        ("ربات رسمی", "badking.Bot"),
        ("Self-bot", "badking.SelfBot"),
        ("FSM", "badking.StatesGroup"),
        ("فیلتر", "badking.F"),
        ("روتر", "badking.Router"),
        ("تاب‌آوری", "badking.RetryPolicy"),
        ("هوش مصنوعی", "badking.AIAssistant"),
        ("پرداخت", "badking.PaymentToolkit"),
    ]
    for label, path in features:
        parts = path.split(".")
        obj: Any = badking
        found = True
        for part in parts[1:]:
            try:
                obj = getattr(obj, part)
            except AttributeError:
                found = False
                break
        print(ok(label, path) if found else warn(label, "در دسترس نیست"))
    print()
    return 0


# ---------- check ----------

def run_check(path: str = ".") -> int:
    """فایل‌های پایتون پروژه را از نظر خطای نحوی می‌سنجد."""
    root = Path(path)
    if not root.exists():
        print(bad("مسیر نیست", str(root)))
        return 1

    files = sorted(root.rglob("*.py"))
    files = [f for f in files if "__pycache__" not in f.parts and ".venv" not in f.parts]

    if not files:
        print(warn("فایل پایتونی پیدا نشد", str(root)))
        return 0

    print()
    print(f"{_c('BADKING check', _BOLD)}  {_c(str(root.resolve()), _DIM)}")
    print(_c("─" * 46, _DIM))

    errors = 0
    for file in files:
        try:
            source = file.read_text(encoding="utf-8")
            compile(source, str(file), "exec")
        except SyntaxError as exc:
            errors += 1
            print(bad(str(file.relative_to(root)), f"خط {exc.lineno}: {exc.msg}"))
        except (OSError, UnicodeDecodeError) as exc:
            errors += 1
            print(bad(str(file.relative_to(root)), str(exc)))

    print()
    if errors == 0:
        print(_c(f"  {len(files)} فایل، بدون خطای نحوی.", _GREEN))
    else:
        print(_c(f"  {errors} فایل خطا دارد از {len(files)}.", _RED))
    print()
    return 0 if errors == 0 else 1


# ---------- test ----------

def run_test(extra: list[str] | None = None) -> int:
    """تست‌های پروژه را با pytest اجرا می‌کند."""
    try:
        import pytest  # noqa: F401
    except ImportError:
        print(bad("pytest نصب نیست", "pip install pytest"))
        return 1

    args = [sys.executable, "-m", "pytest", "-q", *(extra or [])]
    print(_c(f"  {' '.join(args[2:])}", _DIM))
    print()
    return subprocess.call(args)


__all__ = [
    "check_disk",
    "check_env_file",
    "check_git",
    "check_import",
    "check_network",
    "check_optional_deps",
    "check_python",
    "check_session_file",
    "check_token",
    "check_write_permission",
    "run_check",
    "run_doctor",
    "run_info",
    "run_test",
]
