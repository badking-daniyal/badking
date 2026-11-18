"""Rate Limit Engine — صف اولویت + backoff بر اساس retry_after واقعی سرور.

قویتر از aiobale:
  • بودجه جداگانه هر lane (رسمی / self-bot)
  • صف اولویت (پیام مهم جلوتر میرود)
  • یادگیری از retry_after سرور
"""

from __future__ import annotations

import asyncio
import heapq
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass(order=True)
class _Job:
    priority: int
    seq: int
    coro_factory: Callable[[], Awaitable[Any]] = field(compare=False)


class RateLimiter:
    """محدودکننده نرخ با صف اولویت."""

    def __init__(self, rate: float = 2.0, burst: int = 20, *, name: str = "default"):
        self.rate = rate
        self.burst = burst
        self.name = name
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._queue: list[_Job] = []
        self._seq = 0
        self._lock = asyncio.Lock()
        self._worker: asyncio.Task | None = None
        self.penalty_until = 0.0

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last = now

    async def acquire(self) -> None:
        """منتظر تا یک توکن آزاد شود."""
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1 and time.monotonic() >= self.penalty_until:
                    self._tokens -= 1
                    return
                wait = max(0.0, (1 - self._tokens) / self.rate)
                wait = max(wait, self.penalty_until - time.monotonic())
            await asyncio.sleep(min(wait, 1.0) or 0.01)

    def penalize(self, retry_after: float) -> None:
        """بعد از خطای 429، سرور را باور میکنیم."""
        self.penalty_until = time.monotonic() + max(0.1, retry_after)
        self._tokens = 0

    async def submit(self, coro_factory: Callable[[], Awaitable[Any]], priority: int = 0) -> Any:
        """کار را با اولویت وارد صف میکند و نتیجهاش را برمیگرداند."""
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        job = _Job(-priority, self._seq, coro_factory)
        self._seq += 1
        # heappush تکـعنصری: O(log n) بهجای heapify کامل O(n)
        heapq.heappush(self._queue, (job, future))
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run())
        return await future

    async def _run(self) -> None:
        while self._queue:
            job, future = heapq.heappop(self._queue)
            await self.acquire()
            try:
                result = await job.coro_factory()
                if not future.done():
                    future.set_result(result)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)

    async def close(self) -> None:
        if self._worker and not self._worker.done():
            self._worker.cancel()
