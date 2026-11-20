"""زیرساخت دانلود رسانه SelfBot — امن، جریانی و قابل تست.

این ماژول از شبکه مستقل است: فقط مسیر و نحوه نوشتن فایل را مدیریت میکند.
درخواست HTTP و RPC توسط ``SelfBot.download_file`` انجام میشود. جداسازی
اینجا باعث میشود تمام رفتارهای امنیتی (path traversal، فایل ناقص،
محدودیت حجم، atomic replace) بدون حساب واقعی قابل تست باشند.

هیچ شماره فیلد پروتکلی در این فایل حدس زده نشده است — شمارهها در
``hybrid/schema.py`` از سورس رسمی aiobale 0.3.9 تأیید شدهاند.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import unquote, urlparse

DEFAULT_CHUNK_SIZE = 64 * 1024      # aiobale FileURL.chunk_size پیشفرض
DEFAULT_MAX_SIZE = 2 * 1024**3      # 2 GiB سقف پیشفرض قابل تنظیم

# الگوی نام فایل امن: فقط حروف، اعداد، نقطه، خط تیره و زیرخط.
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class DownloadError(Exception):
    """خطای دانلود رسانه (مسیر، حجم، شبکه یا نوشتن)."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint


def sanitize_filename(name: str, *, fallback: str = "file.bin") -> str:
    """پاکسازی نام فایل: حذف مسیرها و کاراکترهای مخرب.

    جلوگیری از Path Traversal: هرگونه ``/``، ``\\`` یا ``..`` حذف میشود.
    نتیجه هرگز خالی نیست و هیچ جداساز مسیری ندارد.
    """
    if not isinstance(name, str):
        return fallback
    # قسمت آخر مسیر (اگر کسی مسیر کامل داد) و سپس unquote (%2e%2e و ...)
    name = name.replace("\\", "/").split("/")[-1]
    try:
        name = unquote(name)
    except Exception:
        pass
    name = name.replace("\\", "/").split("/")[-1]
    cleaned = _SAFE_NAME.sub("_", name).strip("._")
    if not cleaned or cleaned in {".", ".."}:
        return fallback
    # طول نام فایل را محدود میکنیم (NAMELEN روی اکثر سیستمها 255)
    return cleaned[:200]


def filename_from_url(url: str, *, fallback: str = "file.bin") -> str:
    """استخراج نام فایل از مسیر URL (بدون query و fragment)."""
    try:
        path = urlparse(url).path
    except Exception:
        return fallback
    name = path.rsplit("/", 1)[-1] if path else ""
    return sanitize_filename(name, fallback=fallback)


def resolve_destination(
    destination: str | os.PathLike[str] | None,
    *,
    base_dir: str | os.PathLike[str] | None = None,
    filename: str = "",
    fallback_name: str = "file.bin",
) -> Path:
    """تعیین مسیر نهایی با جلوگیری کامل از خروج از ``base_dir``.

    قواعد:
      * ``destination`` میتواند پوشه یا نام فایل باشد.
      * ``base_dir`` مرز مجاز است؛ اگر تنظیم شود، مسیر نهایی حتماً داخل آن است.
      * نام فایل همیشه sanitize میشود (حتی اگر کاربر مسیر مطلق بدهد).
      * در صورت تلاش برای ``..`` یا خروج از مرز → ``DownloadError``.
    """
    base = Path(base_dir).expanduser().resolve() if base_dir else None
    raw = Path(destination).expanduser() if destination is not None else Path(".")

    # تشخیص پوشه بودن مقصد: پسوند نداشته باشد یا صریحاً پوشه موجود باشد.
    is_dir = raw.is_dir() or (destination is not None and not raw.suffix and filename != "")

    if is_dir:
        folder = raw
        name = sanitize_filename(filename, fallback=fallback_name)
    else:
        folder = raw.parent
        name = sanitize_filename(raw.name or filename, fallback=fallback_name)

    target = (folder / name)
    target = target.expanduser()
    if base is not None:
        resolved = target.resolve()
        try:
            resolved.relative_to(base)
        except ValueError:
            raise DownloadError(
                "مسیر دانلود خارج از پوشه مجاز است",
                hint="destination را داخل base_dir قرار بده.",
            ) from None
        return resolved
    return target.absolute()


def unique_path(path: Path) -> Path:
    """اگر فایل وجود دارد، ``name (1).ext`` و ... برگردان (جلوگیری از overwrite)."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for i in range(1, 10000):
        candidate = path.with_name(f"{stem} ({i}){suffix}")
        if not candidate.exists():
            return candidate
    raise DownloadError("تعداد فایلهای تکراری زیاد است", hint="پوشه دیگری انتخاب کن.")


async def write_stream_atomic(
    stream: AsyncIterator[bytes],
    target: Path,
    *,
    max_size: int = DEFAULT_MAX_SIZE,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overwrite: bool = False,
    on_progress: object = None,
) -> int:
    """نوشتن جریان به دیسک بهصورت اتمیک و با مصرف حافظه ثابت.

    قواعد:
      * فایل موقت در همان پوشه (همان filesystem → ``os.replace`` اتمیک است).
      * مجوز 0600 روی سیستمهای POSIX.
      * هر چانک بلافاصله نوشته میشود — کل فایل در RAM بارگذاری نمیشود.
      * تجاوز از ``max_size``، خطای شبکه یا هر استثنا → فایل موقت پاک میشود
        و فایل مقصد (در صورت وجود) دستنخورده میماند.
      * ``on_progress(downloaded, total)`` در صورت ارائه صدا زده میشود.
    """
    if max_size <= 0:
        raise DownloadError("max_size باید مثبت باشد")
    if chunk_size <= 0:
        raise DownloadError("chunk_size باید مثبت باشد")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        target = unique_path(target)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".part", dir=str(target.parent)
    )
    tmp = Path(tmp_name)
    written = 0
    try:
        with os.fdopen(fd, "wb") as fh:
            async for chunk in stream:
                if not chunk:
                    continue
                written += len(chunk)
                if written > max_size:
                    raise DownloadError(
                        "حجم فایل از حد مجاز فراتر رفت",
                        hint=f"max_size={max_size} بایت است.",
                    )
                fh.write(chunk)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        tmp = None  # type: ignore[assignment]
    except DownloadError:
        raise
    except Exception as exc:  # noqa: BLE001 — خطای شبکه/دیسک
        raise DownloadError(f"دانلود ناتمام ماند: {type(exc).__name__}") from exc
    finally:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    if on_progress is not None:
        try:
            result = on_progress(written, written)  # type: ignore[operator]
            if hasattr(result, "__await__"):
                await result
        except Exception:
            pass  # پیشرفت نباید دانلود را خراب کند
    return written
