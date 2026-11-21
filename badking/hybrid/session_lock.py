"""قفل فایل Between-Process برای Session Storage — stdlib خالص.

چرا فایل قفل جداگانه؟
    فایل session با ``os.replace`` جایگزین میشود (atomic write). اگر قفل روی
    خود فایل session میبود، هر نوشتن قفل processهای دیگر را بیاثر میکرد.
    بنابراین قفل روی ``<session>.lock`` میماند که هرگز جایگزین یا حذف نمیشود.

پلتفرم:
    * Windows: ``msvcrt.locking`` (قفل محدوده بایت)
    * POSIX: ``fcntl.flock`` (قفل مشترک/انحصاری advisor)

هر دو stdlibاند و در Python 3.9–3.12 موجوداند — وابستگی جدیدی اضافه نمیشود.

Crash safety:
    قفل به file descriptor متصل است. اگر process بدون آزادسازی بمیرد،
    سیستمعامل قفل را خودکار آزاد میکند — قفل دائمی باقی نمیماند.

Reentrancy:
    در همان thread، اگر قفل همان path قبلاً گرفته شده، دوباره گرفته نمیشود
    (depth شمارش میشود). هماهنگی threadهای همان process توسط RLock جداگانه
    در ``session.py`` انجام میشود تا دو thread با fd متفاوت با هم deadlock نکنند.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
from pathlib import Path
from typing import Iterator

try:  # pragma: no cover — بسته به سیستمعامل
    import msvcrt
except ImportError:  # pragma: no cover
    msvcrt = None  # type: ignore[assignment]

try:  # pragma: no cover
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


class FileLockTimeout(Exception):
    """انتظار برای قفل فایل بیش از حد مجاز طول کشید."""


class FileLockUnavailable(Exception):
    """هیچ مکانیزم قفل فایل در این پلتفرم موجود نیست."""


# وضعیت قفل بهازای thread — برای reentrancy در همان thread.
_local = threading.local()


def lock_path_for(path: str | Path) -> Path:
    """مسیر فایل قفل پایدار (هرگز توسط atomic write جایگزین نمیشود)."""
    p = Path(path)
    return p.with_name(p.name + ".lock")


@contextlib.contextmanager
def cross_process_lock(
    path: str | Path,
    *,
    timeout: float = 30.0,
    poll_interval: float = 0.02,
) -> Iterator[None]:
    """قفل انحصاری Between-Process روی فایل session.

    Args:
        path: مسیر فایل session (فایل قفل مجزا ساخته میشود).
        timeout: حداکثر انتظار به ثانیه. ``0`` یعنی تلاش یکبار و شکست فوری.
        poll_interval: فاصله تلاش مجدد.

    Raises:
        FileLockTimeout: اگر قفل در مدت مشخص به دست نیامد.
        FileLockUnavailable: اگر نه msvcrt و نه fcntl موجود نباشد.
    """
    key = str(Path(path).resolve())
    state = getattr(_local, "state", None)
    if state is not None and state["key"] == key:
        # Reentrant در همان thread — فقط شمارش عمق.
        state["depth"] += 1
        try:
            yield
        finally:
            state["depth"] -= 1
        return

    if msvcrt is None and fcntl is None:  # pragma: no cover
        raise FileLockUnavailable("قفل فایل در این پلتفرم پشتیبانی نمیشود")

    lp = lock_path_for(path)
    lp.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lp), os.O_RDWR | os.O_CREAT, 0o600)
    acquired = False
    try:
        if msvcrt is not None:
            # اطمینان از وجود حداقل یک بایت برای قفل محدوده.
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\x00")
            os.lseek(fd, 0, os.SEEK_SET)
            deadline = time.monotonic() + max(0.0, timeout)
            attempt = 0
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise FileLockTimeout(
                            f"قفل session در مدت {timeout:g} ثانیه به دست نیامد"
                        ) from None
                    attempt += 1
                    # Backoff + jitter: جلوگیری از starvation وقتی چند process
                    # همزمان با فواصل منظم تلاش میکنند (همه با هم برخورد نکنند).
                    delay = min(poll_interval * (1 + attempt // 5), 0.2)
                    time.sleep(delay * (0.5 + (os.urandom(1)[0] / 255.0)))
        else:  # pragma: no cover — روی POSIX اجرا میشود
            deadline = time.monotonic() + max(0.0, timeout)
            attempt = 0
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise FileLockTimeout(
                            f"قفل session در مدت {timeout:g} ثانیه به دست نیامد"
                        ) from None
                    attempt += 1
                    delay = min(poll_interval * (1 + attempt // 5), 0.2)
                    time.sleep(delay * (0.5 + (os.urandom(1)[0] / 255.0)))

        st = {"key": key, "fd": fd, "depth": 1}
        _local.state = st
        try:
            yield
        finally:
            st["depth"] -= 1
            if getattr(_local, "state", None) is st and st["depth"] == 0:
                _local.state = None
    finally:
        if acquired:
            try:
                if msvcrt is not None:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass  # process در حال خروج — OS قفل را آزاد میکند
        os.close(fd)
