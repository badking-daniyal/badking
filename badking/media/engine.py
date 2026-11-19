"""Media Engine — آپلود، دانلود، پیشرفت، کش، اعتبارسنجی.

    from badking.media import MediaEngine

    engine = MediaEngine(bot, cache_dir=".cache/media")

    # دانلود با پیشرفت
    async def on_progress(done, total):
        print(f"{done}/{total}")

    path = await engine.download(file_id, on_progress=on_progress)

    # آپلود با اعتبارسنجی
    await engine.upload(chat_id, "report.pdf")

قواعد امنیتی که این ماژول رعایت می‌کند:

- نام فایل از کاربر هرگز مستقیم استفاده نمی‌شود (Path Traversal).
- حجم قبل از دانلود چک می‌شود.
- MIME Type با پسوند تطبیق داده می‌شود.
- فایل تکراری دوباره دانلود نمی‌شود (کش با هش).
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Union

log = logging.getLogger("badking.media")

ProgressCallback = Callable[[int, int], Union[Awaitable[None], None]]

# پسوندهای مجاز. هر چیز دیگری رد می‌شود.
SAFE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
    ".mp4", ".mkv", ".mov", ".avi", ".webm",
    ".mp3", ".ogg", ".wav", ".m4a", ".flac", ".opus",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".json", ".xml", ".zip", ".rar", ".7z", ".tar", ".gz",
}

# کاراکترهایی که در نام فایل خطرناک‌اند
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class MediaError(Exception):
    """خطای رسانه، با راهنمای رفع."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message}\n  → {self.hint}" if self.hint else self.message


@dataclass
class MediaInfo:
    """اطلاعات یک فایل رسانه‌ای."""

    file_id: str
    file_name: str = ""
    mime_type: str = ""
    size: int = 0
    duration: int = 0
    width: int = 0
    height: int = 0
    thumbnail: str = ""

    @property
    def extension(self) -> str:
        """پسوند با نقطه. اگر نبود، از MIME حدس می‌زند."""
        if self.file_name:
            ext = Path(self.file_name).suffix.lower()
            if ext:
                return ext
        if self.mime_type:
            guessed = mimetypes.guess_extension(self.mime_type)
            if guessed:
                return guessed.lower()
        return ""

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith("image/") or self.extension in {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"
        }

    @property
    def is_video(self) -> bool:
        return self.mime_type.startswith("video/") or self.extension in {
            ".mp4", ".mkv", ".mov", ".avi", ".webm"
        }

    @property
    def is_audio(self) -> bool:
        return self.mime_type.startswith("audio/") or self.extension in {
            ".mp3", ".ogg", ".wav", ".m4a", ".flac", ".opus"
        }

    def human_size(self) -> str:
        """حجم خوانا: «۲.۳ مگابایت»."""
        size = float(self.size)
        for unit in ("بایت", "کیلوبایت", "مگابایت", "گیگابایت"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ترابایت"


def safe_filename(name: str, fallback: str = "file") -> str:
    """نام فایل امن از ورودی نامطمئن.

        safe_filename("../../etc/passwd")   → "passwd"
        safe_filename("a/b\\c.txt")         → "c.txt"
        safe_filename("")                   → "file"
        safe_filename("...")                → "file"

    این تابع تنها جایی است که نام فایل از کاربر پذیرفته می‌شود.
    """
    if not name:
        return fallback

    # فقط بخش آخر مسیر — هر ../ حذف می‌شود
    name = name.replace("\\", "/").split("/")[-1]

    # کاراکترهای خطرناک
    name = _UNSAFE_CHARS.sub("_", name)

    # نقطه و فاصله ابتدا و انتها (ویندوز مشکل دارد)
    name = name.strip(". ")

    if not name or name in {".", ".."}:
        return fallback

    # طول
    if len(name) > 200:
        stem = Path(name).stem[:180]
        name = stem + Path(name).suffix

    return name


def validate_extension(name: str, *, allow: set[str] | None = None) -> str:
    """پسوند را چک می‌کند. خطا اگر مجاز نباشد."""
    ext = Path(name).suffix.lower()
    allowed = allow if allow is not None else SAFE_EXTENSIONS

    if not ext:
        raise MediaError(
            f"فایل {name!r} پسوند ندارد",
            hint="پسوند لازم است تا نوع فایل مشخص شود.",
        )

    if ext not in allowed:
        raise MediaError(
            f"پسوند {ext} مجاز نیست",
            hint=f"پسوندهای مجاز: {', '.join(sorted(allowed)[:10])} ...",
        )

    return ext


def check_mime_matches(name: str, mime_type: str) -> bool:
    """آیا MIME با پسوند می‌خواند؟

    فایلی به نام ``photo.jpg`` با MIME ``application/x-msdownload``
    مشکوک است. این تابع آن را می‌گیرد.
    """
    if not mime_type:
        return True

    ext = Path(name).suffix.lower()
    guessed, _ = mimetypes.guess_type(f"x{ext}")
    if not guessed:
        return True

    # مقایسه گروه اصلی: image/jpeg با image/png هم‌خانواده‌اند
    return guessed.split("/")[0] == mime_type.split("/")[0]


@dataclass
class MediaEngine:
    """مدیریت فایل‌ها: دانلود، آپلود، کش.

    Args:
        bot: کلاینت BADKING.
        cache_dir: پوشه کش. فایل تکراری دوباره دانلود نمی‌شود.
        max_size: حداکثر حجم به بایت. پیش‌فرض ۵۰ مگابایت.
        chunk_size: اندازه هر قطعه در دانلود جریانی.
    """

    bot: Any = None
    cache_dir: str | Path = ".cache/media"
    max_size: int = 50 * 1024 * 1024
    chunk_size: int = 64 * 1024
    _cache: dict[str, Path] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ---------- کش ----------

    def _cache_key(self, file_id: str) -> str:
        return hashlib.sha256(file_id.encode("utf-8")).hexdigest()[:32]

    def cached_path(self, file_id: str) -> Path | None:
        """اگر قبلاً دانلود شده، مسیرش را بده."""
        key = self._cache_key(file_id)
        for entry in self.cache_dir.glob(f"{key}*"):
            if entry.is_file():
                return entry
        return None

    def cache_size(self) -> int:
        """حجم کل کش به بایت."""
        return sum(f.stat().st_size for f in self.cache_dir.glob("*") if f.is_file())

    def clear_cache(self) -> int:
        """کش را پاک می‌کند. تعداد فایل حذف‌شده."""
        count = 0
        for entry in self.cache_dir.glob("*"):
            if entry.is_file():
                entry.unlink()
                count += 1
        return count

    def enforce_disk_limit(self, limit_bytes: int) -> int:
        """اگر کش از حد گذشت، قدیمی‌ترین‌ها را پاک می‌کند."""
        files = sorted(
            (f for f in self.cache_dir.glob("*") if f.is_file()),
            key=lambda f: f.stat().st_mtime,
        )
        total = sum(f.stat().st_size for f in files)
        removed = 0

        while total > limit_bytes and files:
            victim = files.pop(0)
            total -= victim.stat().st_size
            victim.unlink()
            removed += 1

        return removed

    # ---------- اعتبارسنجی ----------

    def validate(self, info: MediaInfo) -> None:
        """قبل از دانلود چک می‌کند. خطا اگر مشکلی بود."""
        if info.size and info.size > self.max_size:
            raise MediaError(
                f"حجم فایل {info.human_size()} از حد {self.max_size // (1024*1024)} مگابایت بیشتر است",
                hint="max_size را بالاتر ببر، یا فایل را کوچک‌تر کن.",
            )

        if info.file_name:
            safe_filename(info.file_name)
            if info.extension:
                validate_extension(info.file_name)

            if info.mime_type and not check_mime_matches(info.file_name, info.mime_type):
                raise MediaError(
                    f"MIME ({info.mime_type}) با پسوند {info.extension} نمی‌خواند",
                    hint="فایل ممکن است جعلی باشد. رد شد.",
                )

    # ---------- دانلود ----------

    async def download(
        self,
        file_id: str,
        *,
        file_name: str = "",
        on_progress: ProgressCallback | None = None,
        use_cache: bool = True,
        force: bool = False,
    ) -> Path:
        """فایل را دانلود می‌کند و مسیر محلی را برمی‌گرداند.

        Args:
            file_id: شناسه فایل در بله.
            file_name: نام دلخواه. اگر خالی باشد از file_id ساخته می‌شود.
            on_progress: تابع پیشرفت ``(done, total)``.
            use_cache: اگر قبلاً دانلود شده، از کش بده.
            force: حتی اگر در کش هست، دوباره دانلود کن.
        """
        if use_cache and not force:
            hit = self.cached_path(file_id)
            if hit:
                log.debug("از کش: %s", hit)
                return hit

        name = safe_filename(file_name, fallback=f"{self._cache_key(file_id)}.bin")
        key = self._cache_key(file_id)
        target = self.cache_dir / f"{key}_{name}"

        if not self.bot:
            raise MediaError(
                "کلاینت تنظیم نشده",
                hint="MediaEngine(bot, ...) — کلاینت را در سازنده بده.",
            )

        try:
            await self.bot.download_file(
                file_id,
                destination=str(target),
                on_progress=on_progress,
            )
        except AttributeError as exc:
            raise MediaError(
                "کلاینت متد download_file ندارد",
                hint="کلاینت باید از badking.Bot باشد.",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise MediaError(
                f"دانلود نشد: {exc}",
                hint="file_id درست است؟ ربات به فایل دسترسی دارد؟",
            ) from exc

        if not target.exists():
            raise MediaError(
                "دانلود تمام شد ولی فایل نیست",
                hint="کلاینت فایل را جای دیگری ذخیره کرده. مسیر را چک کن.",
            )

        size = target.stat().st_size
        if size > self.max_size:
            target.unlink()
            raise MediaError(
                f"فایل دانلودشده {size} بایت است، بیشتر از حد",
                hint="max_size را بالاتر ببر.",
            )

        log.info("دانلود شد: %s (%d بایت)", target.name, size)
        return target

    async def download_many(
        self,
        file_ids: list[str],
        *,
        concurrency: int = 3,
        on_progress: ProgressCallback | None = None,
    ) -> list[Path | None]:
        """چند فایل را هم‌زمان دانلود می‌کند.

        خطای یکی بقیه را متوقف نمی‌کند — جای خطا ``None`` می‌آید.
        """
        import asyncio

        semaphore = asyncio.Semaphore(concurrency)

        async def one(file_id: str) -> Path | None:
            async with semaphore:
                try:
                    return await self.download(file_id, on_progress=on_progress)
                except MediaError as exc:
                    log.warning("دانلود %s نشد: %s", file_id, exc)
                    return None

        return list(await asyncio.gather(*(one(f) for f in file_ids)))

    # ---------- آپلود ----------

    async def upload(
        self,
        chat_id: int | str,
        path: str | Path,
        *,
        caption: str = "",
        as_type: str = "auto",
        on_progress: ProgressCallback | None = None,
    ) -> Any:
        """فایل را آپلود می‌کند.

        Args:
            as_type: ``auto`` (از پسوند حدس می‌زند)، ``photo``، ``video``،
                ``audio``، ``voice``، ``document``.
        """
        path = Path(path)

        if not path.is_file():
            raise MediaError(
                f"فایل نیست: {path}",
                hint="مسیر را چک کن.",
            )

        size = path.stat().st_size
        if size > self.max_size:
            raise MediaError(
                f"حجم {size} بایت از حد بیشتر است",
                hint="max_size را بالاتر ببر.",
            )

        validate_extension(path.name)

        if not self.bot:
            raise MediaError("کلاینت تنظیم نشده", hint="MediaEngine(bot, ...)")

        kind = as_type
        if kind == "auto":
            ext = path.suffix.lower()
            if ext in {".jpg", ".jpeg", ".png", ".webp"}:
                kind = "photo"
            elif ext in {".mp4", ".mkv", ".mov", ".webm"}:
                kind = "video"
            elif ext in {".mp3", ".m4a", ".flac"}:
                kind = "audio"
            elif ext in {".ogg", ".opus"}:
                kind = "voice"
            else:
                kind = "document"

        method = getattr(self.bot, f"send_{kind}", None)
        if method is None:
            raise MediaError(
                f"کلاینت متد send_{kind} ندارد",
                hint="as_type را عوض کن: photo, video, audio, voice, document",
            )

        try:
            return await method(chat_id, str(path), caption=caption)
        except Exception as exc:  # noqa: BLE001
            raise MediaError(
                f"آپلود نشد: {exc}",
                hint="حجم مجاز بله را چک کن. ربات در آن چت اجازه ارسال دارد؟",
            ) from exc

    # ---------- اطلاعات ----------

    async def info(self, file_id: str) -> MediaInfo:
        """اطلاعات فایل را از سرور می‌گیرد."""
        if not self.bot:
            raise MediaError("کلاینت تنظیم نشده", hint="MediaEngine(bot, ...)")

        try:
            raw = await self.bot.get_file(file_id)
        except Exception as exc:  # noqa: BLE001
            raise MediaError(
                f"اطلاعات فایل نیامد: {exc}",
                hint="file_id معتبر است؟",
            ) from exc

        if isinstance(raw, MediaInfo):
            return raw

        return MediaInfo(
            file_id=file_id,
            file_name=getattr(raw, "file_name", "") or "",
            mime_type=getattr(raw, "mime_type", "") or "",
            size=getattr(raw, "file_size", 0) or 0,
            duration=getattr(raw, "duration", 0) or 0,
            width=getattr(raw, "width", 0) or 0,
            height=getattr(raw, "height", 0) or 0,
            thumbnail=getattr(raw, "thumbnail", "") or "",
        )

    def disk_usage(self) -> dict[str, Any]:
        """وضعیت دیسک کش."""
        total, used, free = shutil.disk_usage(self.cache_dir)
        return {
            "cache_bytes": self.cache_size(),
            "cache_files": len(list(self.cache_dir.glob("*"))),
            "disk_total": total,
            "disk_used": used,
            "disk_free": free,
        }


__all__ = [
    "MediaEngine",
    "MediaError",
    "MediaInfo",
    "SAFE_EXTENSIONS",
    "check_mime_matches",
    "safe_filename",
    "validate_extension",
]
