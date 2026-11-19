"""ابزارهای عمومی BADKING.

هر چیزی که در کار روزمره لازم می‌شود و جای دیگری ندارد: برش متن، ساخت
شناسه، استخراج توکن دعوت، محدودکننده نرخ، نوار پیشرفت، و پارس کردن
لیست int64 که بله در پاسخ‌ها برمی‌گرداند.
"""

from __future__ import annotations

import re
import secrets
import sys
import time
from typing import Any, Callable, Iterable, List, Optional, Sequence


# ---------- متن ----------

def smart_split_text(text: str, max_length: int = 4000) -> List[str]:
    """برش متن بلند به تکه‌های حداکثر `max_length`، بدون شکستن کلمه.

    اول آخرین خط جدید داخل محدوده را می‌گیرد، بعد آخرین فاصله، و اگر هیچ
    کدام نبود برش سخت می‌زند. همان کاری که کلاینت رسمی برای پیام‌های بلند
    می‌کند.

        for part in smart_split_text(long_text):
            await bot.send_message(peer, part)
    """
    if not text:
        return [""]
    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    remaining = text

    while len(remaining) > max_length:
        split_idx = remaining.rfind("\n", 0, max_length)
        if split_idx == -1 or split_idx == 0:
            split_idx = remaining.rfind(" ", 0, max_length)
        if split_idx == -1 or split_idx == 0:
            split_idx = max_length

        chunk = remaining[:split_idx].rstrip()
        if chunk:
            chunks.append(chunk)

        remaining = remaining[split_idx:]
        if remaining.startswith("\r\n"):
            remaining = remaining[2:]
        elif remaining.startswith("\n") or remaining.startswith(" "):
            remaining = remaining[1:]

    if remaining.strip():
        chunks.append(remaining)

    return chunks or [text]


def split_by_length(text: str, max_length: int = 4000) -> List[str]:
    """برش سخت، بدون توجه به کلمه. برای وقتی مرز مهم نیست."""
    if not text:
        return [""]
    return [text[i : i + max_length] for i in range(0, len(text), max_length)]


# ---------- شناسه ----------

def generate_id(length: int = 16) -> int:
    """شناسه تصادفی با `length` رقم، بدون صفر پیشرو.

    بله برای `random_id` در ساخت گروه و ارسال پیام عدد می‌خواهد، نه رشته.
    """
    if length < 1:
        raise ValueError("طول باید حداقل ۱ باشد")
    first = str(secrets.randbelow(9) + 1)
    rest = "".join(str(secrets.randbelow(10)) for _ in range(length - 1))
    return int(first + rest)


def random_id() -> int:
    """شناسه ۱۶ رقمی، آماده برای random_id."""
    return generate_id(16)


# ---------- لینک ----------

_JOIN_RE = re.compile(r"(?:https?://)?(?:ble|bale)\.ir/join/([A-Za-z0-9_-]+)")
_USERNAME_RE = re.compile(r"^@?([A-Za-z][A-Za-z0-9_]{3,31})$")


def extract_join_token(text: str) -> Optional[str]:
    """توکن دعوت گروه را از لینک یا رشته خالی بیرون می‌کشد.

        extract_join_token("https://ble.ir/join/AbCd123")  # "AbCd123"
        extract_join_token("AbCd123")                      # "AbCd123"
    """
    if not text:
        return None
    match = _JOIN_RE.search(text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]+", text):
        return text
    return None


def extract_username(text: str) -> Optional[str]:
    """یوزرنیم را از `@name` یا لینک `ble.ir/name` بیرون می‌کشد."""
    if not text:
        return None
    text = text.strip()
    if "/" in text:
        text = text.rstrip("/").rsplit("/", 1)[-1]
    match = _USERNAME_RE.match(text)
    return match.group(1) if match else None


# ---------- عدد صحیح ۶۴ بیتی ----------

def decode_int64_list(data: bytes | str) -> List[int]:
    """لیست int64 را از varint های پشت‌سرهم می‌خواند.

    بله بعضی پاسخ‌ها (مثل لیست id ها) را به‌صورت بایت خام برمی‌گرداند، نه
    فیلد تودرتو. این تابع آن را به لیست پایتونی تبدیل می‌کند.
    """
    if isinstance(data, str):
        data = bytes.fromhex(data)

    out: List[int] = []
    shift = 0
    value = 0
    for byte in data:
        value |= (byte & 0x7F) << shift
        if byte & 0x80:
            shift += 7
            if shift > 63:
                raise ValueError("varint بیش از ۶۴ بیت")
        else:
            out.append(value)
            value = 0
            shift = 0
    if shift:
        raise ValueError("varint ناتمام در انتهای داده")
    return out


def encode_int64_list(values: Iterable[int]) -> bytes:
    """عکس `decode_int64_list`: لیست اعداد را به varint پشت‌سرهم تبدیل می‌کند."""
    out = bytearray()
    for v in values:
        v = int(v)
        if v < 0:
            v += 1 << 64
        while True:
            byte = v & 0x7F
            v >>= 7
            if v:
                out.append(byte | 0x80)
            else:
                out.append(byte)
                break
    return bytes(out)


# ---------- نمایش حجم و پیشرفت ----------

def format_bytes(size_bytes: float) -> str:
    """حجم را خوانا می‌کند: ۱.۵ MB، ۸۲۰ KB، ..."""
    if size_bytes < 1024:
        return f"{size_bytes:.0f} B"
    if size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} MB"
    return f"{size_bytes / 1024**3:.2f} GB"


def create_progress_bar(
    description: str = "انتقال",
    bar_length: int = 25,
    fill_char: str = "█",
    empty_char: str = "░",
) -> Callable[[int, Optional[int]], None]:
    """نوار پیشرفت ترمینال، آماده برای upload_file / download_file.

        cb = create_progress_bar("آپلود")
        await bot.upload_file("video.mp4", progress_callback=cb)
    """
    start_time = time.time()
    last_update = 0.0

    def progress_callback(current: int, total: Optional[int] = None) -> None:
        nonlocal last_update
        now = time.time()
        if total and current < total and (now - last_update) < 0.1:
            return
        last_update = now

        elapsed = max(0.001, now - start_time)
        speed = current / elapsed
        speed_str = f"{format_bytes(speed)}/s"

        if total and total > 0:
            percent = min(100.0, (current / total) * 100.0)
            filled = int(bar_length * current // total)
            bar = fill_char * filled + empty_char * (bar_length - filled)
            size_str = f"{format_bytes(current)} / {format_bytes(total)}"
            output = f"\r{description}: [{bar}] {percent:.1f}% ({size_str}) {speed_str}"
        else:
            output = f"\r{description}: {format_bytes(current)} {speed_str}"

        sys.stdout.write(output)
        sys.stdout.flush()

        if total and current >= total:
            sys.stdout.write("\n")
            sys.stdout.flush()

    return progress_callback


# ---------- محدودکننده نرخ ----------

class Throttle:
    """فاصله‌گذاری بین فراخوانی‌ها تا سرور flood-wait ندهد.

        throttle = Throttle(rate=0.05)   # ۲۰ درخواست در ثانیه
        await throttle.run(bot.send_message, peer, "سلام")
    """

    def __init__(self, rate: float = 0.05, max_retries: int = 3) -> None:
        self.rate = rate
        self.max_retries = max_retries
        self._last = 0.0

    async def run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        import asyncio

        now = time.time()
        elapsed = now - self._last
        if elapsed < self.rate:
            await asyncio.sleep(self.rate - elapsed)
        self._last = time.time()

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt == self.max_retries:
                    break
                await asyncio.sleep(attempt * 0.5)
        raise last_exc  # type: ignore[misc]


# ---------- متن فارسی ----------

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"


def to_persian_digits(value: Any) -> str:
    """ارقام لاتین را فارسی می‌کند. برای نمایش، نه برای محاسبه."""
    return "".join(
        _PERSIAN_DIGITS[int(ch)] if ch.isdigit() else ch for ch in str(value)
    )


def to_english_digits(value: Any) -> str:
    """ارقام فارسی و عربی را لاتین می‌کند. قبل از پارس کردن عدد لازم است."""
    out = []
    for ch in str(value):
        if ch in _PERSIAN_DIGITS:
            out.append(str(_PERSIAN_DIGITS.index(ch)))
        elif ch in _ARABIC_DIGITS:
            out.append(str(_ARABIC_DIGITS.index(ch)))
        else:
            out.append(ch)
    return "".join(out)


def normalize_phone(phone: str) -> str:
    """شماره را به شکل `98912...` درمی‌آورد که بله می‌خواهد.

        normalize_phone("۰۹۱۲۳۴۵۶۷۸۹")  # "989123456789"
        normalize_phone("+98 912 345 6789")  # "989123456789"
    """
    digits = re.sub(r"\D", "", to_english_digits(phone))
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = "98" + digits[1:]
    if not digits.startswith("98"):
        digits = "98" + digits
    return digits


__all__ = [
    "Throttle",
    "create_progress_bar",
    "decode_int64_list",
    "encode_int64_list",
    "extract_join_token",
    "extract_username",
    "format_bytes",
    "generate_id",
    "normalize_phone",
    "random_id",
    "smart_split_text",
    "split_by_length",
    "to_english_digits",
    "to_persian_digits",
]
