"""موتور تاب‌آوری: تلاش مجدد، مدارشکن، و صف درخواست.

این‌ها همان چیزهایی هستند که توسعه‌دهنده مجبور است در هر پروژه از صفر
بنویسد. اینجا یک بار نوشته شده‌اند و کار می‌کنند.

    from badking.resilience import RetryPolicy, CircuitBreaker, RequestQueue

    policy = RetryPolicy(attempts=3, base_delay=0.5)
    result = await policy.run(bot.send_message, peer, "سلام")
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Generic, TypeVar

from .core.errors import (
    BADKINGError,
    CircuitOpenError,
    RateLimitError,
    TimeoutError_,
)

T = TypeVar("T")


# ---------- تلاش مجدد ----------

class Backoff(str, Enum):
    """نحوه رشد فاصله بین تلاش‌ها."""

    FIXED = "fixed"
    """همیشه همان مقدار."""
    LINEAR = "linear"
    """۱، ۲، ۳، ۴ برابر base."""
    EXPONENTIAL = "exponential"
    """۱، ۲، ۴، ۸ برابر base — پیش‌فرض."""


@dataclass
class RetryPolicy:
    """سیاست تلاش مجدد با backoff.

        policy = RetryPolicy(attempts=4, base_delay=0.5, max_delay=8.0)
        await policy.run(bot.send_message, peer, "سلام")

    خطاهایی که `retryable` ندارند (مثل ValidationError) دوباره تلاش نمی‌شوند —
    تلاش مجدد روی ورودی غلط فقط وقت تلف کردن است.
    """

    attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 30.0
    backoff: Backoff = Backoff.EXPONENTIAL
    jitter: float = 0.1
    """تا این نسبت تصادفی به تاخیر اضافه می‌شود تا همه کلاینت‌ها هم‌زمان نزنند."""
    retry_on: tuple[type[BaseException], ...] = (Exception,)
    give_up_on: tuple[type[BaseException], ...] = ()
    on_retry: Callable[[int, BaseException, float], None] | None = None

    def delay_for(self, attempt: int) -> float:
        """تاخیر تلاش شماره `attempt` (از ۱)."""
        if self.backoff is Backoff.FIXED:
            delay = self.base_delay
        elif self.backoff is Backoff.LINEAR:
            delay = self.base_delay * attempt
        else:
            delay = self.base_delay * (2 ** (attempt - 1))

        delay = min(delay, self.max_delay)
        if self.jitter:
            delay += delay * self.jitter * random.random()
        return delay

    def should_retry(self, exc: BaseException) -> bool:
        """آیا این خطا ارزش تلاش مجدد دارد؟"""
        if isinstance(exc, self.give_up_on):
            return False
        if isinstance(exc, BADKINGError):
            # خطای غیرقابل تکرار (ورودی غلط، مجوز) را دوباره نزن
            return exc.retryable
        return isinstance(exc, self.retry_on)

    async def run(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """تابع را با تلاش مجدد اجرا می‌کند."""
        last: BaseException | None = None

        for attempt in range(1, self.attempts + 1):
            try:
                return await func(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001
                last = exc
                if attempt >= self.attempts or not self.should_retry(exc):
                    raise

                # اگر سرور گفته چند ثانیه صبر کن، همان را رعایت کن
                if isinstance(exc, RateLimitError) and exc.retry_after:
                    delay = min(float(exc.retry_after), self.max_delay)
                else:
                    delay = self.delay_for(attempt)

                if self.on_retry:
                    self.on_retry(attempt, exc, delay)
                await asyncio.sleep(delay)

        raise last  # type: ignore[misc]


# ---------- مدارشکن ----------

class CircuitState(str, Enum):
    CLOSED = "closed"
    """سالم — درخواست‌ها رد می‌شوند."""
    OPEN = "open"
    """خراب — درخواست‌ها فوراً رد می‌شوند."""
    HALF_OPEN = "half_open"
    """در حال تست — یک درخواست آزمایشی می‌رود."""


@dataclass
class CircuitBreaker:
    """مدارشکن: وقتی سرور پیاپی خطا می‌دهد، به‌جای زدن بی‌فایده، صبر می‌کند.

        breaker = CircuitBreaker(failure_threshold=5, cooldown=30.0)
        await breaker.call(bot.send_message, peer, "سلام")

    چرا لازم است: وقتی سرور بله پایین است، ۱۰۰۰ درخواست پشت‌سرهم فقط
    وضعیت را بدتر می‌کند و لاگ را پر می‌کند. مدارشکن بعد از ۵ خطا باز
    می‌شود، ۳۰ ثانیه هیچ درخواستی نمی‌فرستد، بعد یک درخواست آزمایشی
    می‌زند؛ اگر جواب داد، بسته می‌شود.
    """

    failure_threshold: int = 5
    cooldown: float = 30.0
    success_threshold: int = 1
    """چند موفقیت پیاپی در حالت half-open لازم است تا کامل بسته شود."""

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _successes: int = field(default=0, init=False)
    _opened_at: float = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        """وضعیت فعلی، با در نظر گرفتن اینکه cooldown تمام شده یا نه."""
        if self._state is CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self.cooldown:
                self._state = CircuitState.HALF_OPEN
                self._successes = 0
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state is CircuitState.OPEN

    def record_success(self) -> None:
        """یک موفقیت ثبت می‌کند."""
        self._failures = 0
        if self._state is CircuitState.HALF_OPEN:
            self._successes += 1
            if self._successes >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._successes = 0
        else:
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """یک خطا ثبت می‌کند؛ اگر به آستانه رسید، مدار باز می‌شود."""
        self._failures += 1
        if self._state is CircuitState.HALF_OPEN:
            self._open()
        elif self._failures >= self.failure_threshold:
            self._open()

    def _open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()

    def reset(self) -> None:
        """دستی به حالت سالم برمی‌گردد."""
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._successes = 0
        self._opened_at = 0.0

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """تابع را با محافظت مدارشکن اجرا می‌کند."""
        if self.state is CircuitState.OPEN:
            raise CircuitOpenError(
                f"مدارشکن باز است ({self._failures} خطای پیاپی). "
                f"{self.cooldown:.0f} ثانیه صبر می‌کند.",
                hint="سرور بله احتمالاً پایین است. کمی بعد دوباره تلاش کن.",
            )

        try:
            result = await func(*args, **kwargs)
        except BaseException:
            self.record_failure()
            raise
        else:
            self.record_success()
            return result


# ---------- صف درخواست ----------

@dataclass
class RequestQueue:
    """صف درخواست با محدودیت هم‌زمانی.

        queue = RequestQueue(concurrency=5, rate=20.0)
        await queue.submit(bot.send_message, peer, "سلام")

    `concurrency` سقف درخواست هم‌زمان است (backpressure)، و `rate` سقف
    درخواست در ثانیه. بدون این دو، ارسال انبوه به flood-wait می‌خورد.
    """

    concurrency: int = 5
    rate: float = 0.0
    """درخواست در ثانیه. صفر یعنی بی‌نهایت."""
    max_pending: int = 0
    """سقف صف انتظار. صفر یعنی بی‌نهایت."""

    _semaphore: asyncio.Semaphore | None = field(default=None, init=False, repr=False)
    _last_call: float = field(default=0.0, init=False)
    _lock: asyncio.Lock | None = field(default=None, init=False, repr=False)
    _pending: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.concurrency < 1:
            raise ValueError("concurrency باید حداقل ۱ باشد")
        if self.rate < 0:
            raise ValueError("rate نمی‌تواند منفی باشد")

    def _ensure(self) -> None:
        """قفل‌ها را در حلقه رویداد فعلی می‌سازد (نه در سازنده)."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.concurrency)
        if self._lock is None:
            self._lock = asyncio.Lock()

    @property
    def pending(self) -> int:
        """چند درخواست در صف است."""
        return self._pending

    async def submit(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """کار را در صف می‌گذارد و نتیجه را برمی‌گرداند."""
        self._ensure()
        assert self._semaphore is not None and self._lock is not None

        if self.max_pending and self._pending >= self.max_pending:
            raise BADKINGError(
                f"صف پر است ({self._pending} درخواست در انتظار)",
                hint="max_pending را بیشتر کن یا concurrency را بالا ببر.",
            )

        self._pending += 1
        try:
            async with self._semaphore:
                if self.rate > 0:
                    async with self._lock:
                        now = time.monotonic()
                        wait = (1.0 / self.rate) - (now - self._last_call)
                        if wait > 0:
                            await asyncio.sleep(wait)
                        self._last_call = time.monotonic()
                return await func(*args, **kwargs)
        finally:
            self._pending -= 1


# ---------- ترکیب همه ----------

@dataclass
class ResilientCaller:
    """ترکیب صف + مدارشکن + تلاش مجدد در یک شیء.

        caller = ResilientCaller()
        await caller(bot.send_message, peer, "سلام")

    ترتیب اجرا از بیرون به درون: صف → مدارشکن → تلاش مجدد. یعنی تلاش
    مجدد داخل مدارشکن است، پس یک خطای نهایی یک شکست حساب می‌شود، نه سه.
    """

    queue: RequestQueue = field(default_factory=RequestQueue)
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    policy: RetryPolicy = field(default_factory=RetryPolicy)

    async def __call__(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        return await self.queue.submit(
            self.breaker.call,
            self.policy.run,
            func,
            *args,
            **kwargs,
        )


__all__ = [
    "Backoff",
    "CircuitBreaker",
    "CircuitState",
    "RequestQueue",
    "ResilientCaller",
    "RetryPolicy",
]
