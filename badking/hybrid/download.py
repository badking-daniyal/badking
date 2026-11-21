"""زیرساخت دانلود رسانه SelfBot — امن، جریانی و قابل تست.

این ماژول از شبکه مستقل است: فقط مسیر و نحوه نوشتن فایل را مدیریت میکند.
درخواست HTTP و RPC توسط ``SelfBot.download_file`` انجام میشود. جداسازی
اینجا باعث میشود تمام رفتارهای امنیتی (path traversal، فایل ناقص،
محدودیت حجم، atomic replace) بدون حساب واقعی قابل تست باشند.

هیچ شماره فیلد پروتکلی در این فایل حدس زده نشده است — شمارهها در
``hybrid/schema.py`` از سورس رسمی aiobale 0.3.9 تأیید شدهاند.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import tempfile
import time
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import unquote, urljoin, urlparse

DEFAULT_CHUNK_SIZE = 64 * 1024      # aiobale FileURL.chunk_size پیشفرض
DEFAULT_MAX_SIZE = 2 * 1024**3      # 2 GiB سقف پیشفرض قابل تنظیم

# الگوی نام فایل امن: فقط حروف، اعداد، نقطه، خط تیره و زیرخط.
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

# نامهای رزروشده دستگاه در ویندوز — حتی با پسوند (CON.txt) قابل استفاده نیستند.
_WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})


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
    cleaned = cleaned[:200]
    # نام رزرو ویندوز (با یا بدون پسوند) روی برخی سیستمها نوشتن را خراب میکند.
    stem = cleaned.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED:
        return fallback
    return cleaned


# رنجهایی که پرچمهای استاندارد ipaddress بهتنهایی پوشش نمیدهند.
# CGNAT (RFC 6598) و benchmarking (RFC 2544) میتوانند به شبکه داخلی منتهی شوند.
_EXTRA_BLOCKED_NETWORKS = (
    ipaddress.ip_network("100.64.0.0/10"),    # CGNAT / shared address space
    ipaddress.ip_network("192.0.0.0/24"),     # IETF protocol assignments
    ipaddress.ip_network("198.18.0.0/15"),    # benchmarking
    ipaddress.ip_network("169.254.0.0/16"),   # link-local (صریحتر از پرچم)
    ipaddress.ip_network("0.0.0.0/8"),        # "this network" — شامل 0.0.0.0
)

# پورتهایی که معمولاً سرویس داخلیاند و نباید توسط URL دانلود هدف قرار گیرند.
_BLOCKED_PORTS = frozenset({
    21, 22, 23, 25, 53, 110, 143, 389, 445, 465, 587, 993, 995,
    1433, 1521, 3306, 3389, 5432, 6379, 7001, 8080, 8443, 9200, 27017,
})


def is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """آیا IP برای اتصال دانلود ایمن (عمومی و قابل مسیریابی) است؟

    برخلاف تکیه صرف به پرچمهای ``ipaddress``، رنجهای CGNAT و benchmarking
    و IPv4-mapped IPv6 را هم صریحاً رد میکند. IPv4-mapped حتی اگر آدرس
    عمومی را بپوشاند، توسط ``is_private`` پرچم میخورد و اینجا هم رد میشود.
    """
    if ip.version == 6 and getattr(ip, "ipv4_mapped", None) is not None:
        return False
    if (ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_unspecified or ip.is_multicast or ip.is_reserved):
        return False
    for net in _EXTRA_BLOCKED_NETWORKS:
        if ip.version == net.version and ip in net:
            return False
    return True


def _validate_host_and_port(parsed) -> tuple[str, int]:
    """اعتبارسنجی میزبان و پورت URL دانلود؛ (host, port) برمیگرداند."""
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise DownloadError(
            "فقط URLهای HTTP/HTTPS برای دانلود مجازاند",
            hint="URL برگشتی از سرور بله غیرقابلقبول است.",
        )
    # userinfo (user:pass@host) میتواند hostname را مبهم کند — رد میشود.
    if parsed.username is not None or parsed.password is not None:
        raise DownloadError(
            "URL دانلود نباید شامل اطلاعات کاربری باشد",
            hint="سرور URL نامعتبر برگردانده است (SSRF مسدود شد).",
        )
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise DownloadError("پورت URL دانلود نامعتبر است") from exc
    if port in _BLOCKED_PORTS:
        raise DownloadError(
            "اتصال به این پورت برای دانلود مجاز نیست",
            hint="سرور URL داخلی برگردانده است (SSRF مسدود شد).",
        )
    return parsed.hostname, port


def resolve_validated_ips(url: str) -> tuple[str, int, list[str]]:
    """URL را اعتبارسنجی و IPهای عمومی آن را برگرداند.

    Returns:
        ``(host, port, ips)`` — ``ips`` لیست رشته IP تأییدشده است.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise DownloadError("URL دانلود نامعتبر است") from exc
    host, port = _validate_host_and_port(parsed)
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not is_public_ip(literal):
            raise DownloadError(
                "دانلود از آدرس خصوصی/داخلی مجاز نیست",
                hint="سرور URL داخلی برگردانده است (SSRF مسدود شد).",
            )
        return host, port, [str(literal)]
    try:
        infos = socket.getaddrinfo(host, port)
    except (socket.gaierror, OSError) as exc:
        # Fail-Closed: بدون IP تأییدشده نباید هیچ اتصالی برقرار شود.
        # بازگشت لیست خالی در اینجا به معنای آزاد کردن مسیر اتصال بدون
        # Pinning است — پس صریحاً خطا میدهیم.
        raise DownloadError(
            "نمیتوان میزبان دانلود را resolve کرد؛ اتصال مسدود شد",
            hint="DNS دردسترس نیست یا پاسخ نامعتبر است.",
        ) from exc
    ips: list[str] = []
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except (ValueError, IndexError, TypeError) as exc:
            # پاسخ DNS نامعتبر — Fail-Closed، نه نادیده گرفتن رکورد.
            raise DownloadError(
                "پاسخ DNS نامعتبر است؛ اتصال مسدود شد",
                hint="سرور DNS رکورد IP قابلقبولی برنگرداند.",
            ) from exc
        if not is_public_ip(ip):
            raise DownloadError(
                "دانلود از آدرس خصوصی/داخلی مجاز نیست",
                hint="سرور URL داخلی برگردانده است (SSRF مسدود شد).",
            )
        text = str(ip)
        if text not in ips:
            ips.append(text)
    if not ips:
        # DNS پاسخ خالی داد — Fail-Closed.
        raise DownloadError(
            "میزبان دانلود هیچ IP قابلاعتمادی ندارد؛ اتصال مسدود شد",
            hint="پاسخ DNS خالی است.",
        )
    return host, port, ips


def validate_download_url(url: str) -> str:
    """جلوگیری از SSRF: فقط HTTP(S) با میزبان عمومی مجاز است.

    فقط schemeهای ``https`` / ``http`` پذیرفته میشوند، userinfo و پورتهای
    داخلی رد میشوند، و تمام IPهای حاصل از DNS بررسی میشوند.

    نکته: این تابع تنها اعتبارسنجی است، نه محافظت در برابر DNS rebinding.
    برای حذف rebinding، ``download_file`` از IP پینشده (module ``ssrf``)
    استفاده میکند تا اتصال دقیقاً به IP تأییدشده برود.
    """
    resolve_validated_ips(url)
    return url


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
    deadline: float | None = None,
) -> int:
    """نوشتن جریان به دیسک بهصورت اتمیک و با مصرف حافظه ثابت.

    قواعد:
      * فایل موقت در همان پوشه (همان filesystem → ``os.replace`` اتمیک است).
      * مجوز 0600 روی سیستمهای POSIX.
      * هر چانک بلافاصله نوشته میشود — کل فایل در RAM بارگذاری نمیشود.
      * تجاوز از ``max_size``، خطای شبکه یا هر استثنا → فایل موقت پاک میشود
        و فایل مقصد (در صورت وجود) دستنخورده میماند.
      * ``on_progress(downloaded, total)`` در صورت ارائه صدا زده میشود.
      * ``deadline`` (ثانیه) مهلت مطلق کل دانلود است — جلوی Slow HTTP
        Trickle را میگیرد (سروری که هر چند ثانیه یک بایت میفرستد).
        ``None`` یعنی محدودیتی اضافه نمیشود (رفتار نسخههای قبل).
    """
    if max_size <= 0:
        raise DownloadError("max_size باید مثبت باشد")
    if chunk_size <= 0:
        raise DownloadError("chunk_size باید مثبت باشد")
    ends_at = time.monotonic() + deadline if deadline is not None else None

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
                if ends_at is not None and time.monotonic() > ends_at:
                    raise DownloadError(
                        "زمان دانلود از حد مجاز فراتر رفت",
                        hint="سرور خیلی کند پاسخ میدهد (Slow HTTP Trickle).",
                    )
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
