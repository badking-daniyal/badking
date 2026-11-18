"""Scheduler/Cron + Job Queue — کارهای زمانبندیشده و پسزمینهای."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable


@dataclass(order=True)
class ScheduledJob:
    run_at: float
    seq: int
    func: Callable[..., Awaitable[Any]] = field(compare=False)
    kwargs: dict[str, Any] = field(default_factory=dict, compare=False)
    repeat: float | None = field(default=None, compare=False)


class Scheduler:
    """زمانبند ساده بدون وابستگی (جایگزین سبک cron)."""

    def __init__(self):
        self._queue: list[ScheduledJob] = []
        self._seq = 0
        self._task: asyncio.Task | None = None
        self._running = False

    def _now(self) -> float:
        return datetime.now().timestamp()

    def schedule(self, func: Callable[..., Awaitable[Any]], *, delay: float | None = None,
                 at: datetime | None = None, repeat: float | None = None,
                 **kwargs: Any) -> ScheduledJob:
        if at is not None:
            run_at = at.timestamp()
        elif delay is not None:
            run_at = self._now() + delay
        else:
            run_at = self._now()
        job = ScheduledJob(run_at, self._seq, func, kwargs, repeat)
        self._seq += 1
        import heapq
        heapq.heappush(self._queue, job)
        return job

    def every(self, seconds: float, func: Callable[..., Awaitable[Any]], **kwargs: Any) -> ScheduledJob:
        return self.schedule(func, delay=seconds, repeat=seconds, **kwargs)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        import heapq
        while self._running:
            now = self._now()
            due = []
            while self._queue and self._queue[0].run_at <= now:
                due.append(heapq.heappop(self._queue))
            for job in due:
                asyncio.create_task(self._execute(job))
            wait = max(0.0, self._queue[0].run_at - now) if self._queue else 0.5
            await asyncio.sleep(min(max(wait, 0.01), 1.0))

    async def _execute(self, job: ScheduledJob) -> None:
        try:
            await job.func(**job.kwargs)
        except Exception:
            import logging
            logging.getLogger("badking.scheduler").exception("خطا در job")
        if job.repeat:
            # زمان بعدی را از زمان برنامهریزی شده حساب کن تا drift تجمعی نشود
            job.run_at += job.repeat
            # اگر اجرا خیلی طول کشید و زمان از دست رفت، دوباره به حال حاضر برگرد
            if job.run_at <= self._now():
                job.run_at = self._now() + job.repeat
            import heapq
            heapq.heappush(self._queue, job)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()


class JobQueue:
    """صف کارهای پسزمینهای با تعداد worker مشخص."""

    def __init__(self, workers: int = 4):
        self.workers = workers
        self._queue: asyncio.Queue = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    async def submit(self, func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> None:
        await self._queue.put((func, args, kwargs))

    async def _worker(self) -> None:
        while True:
            func, args, kwargs = await self._queue.get()
            try:
                await func(*args, **kwargs)
            except Exception:
                import logging
                logging.getLogger("badking.jobs").exception("خطا در worker")
            finally:
                self._queue.task_done()

    async def start(self) -> None:
        for _ in range(self.workers):
            self._tasks.append(asyncio.create_task(self._worker()))

    async def join(self) -> None:
        await self._queue.join()

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
