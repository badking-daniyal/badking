"""Benchmark ساده BADKING — اندازهگیری واقعی، بدون ادعای مقایسهای.

    python benchmarks/bench_core.py

معیارها (طبق بخش ۲۳ سند):
- Requests Per Second
- Average / P95 / P99 Latency
- Memory Consumption
- Startup Time

این benchmark فقط BADKING را اندازه میگیرد. مقایسه با aiobale فقط در
شرایط یکسان و با نصب هر دو بسته معتبر است — فعلاً ادعای مقایسهای نمیکنیم.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class BenchResult:
    name: str
    iterations: int
    total_seconds: float
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def rps(self) -> float:
        if self.total_seconds <= 0:
            return 0.0
        return self.iterations / self.total_seconds

    @property
    def avg_ms(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    def percentile(self, p: float) -> float:
        """P95/P99 latency."""
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        index = min(len(ordered) - 1, int(len(ordered) * p / 100))
        return ordered[index]

    @property
    def p95_ms(self) -> float:
        return self.percentile(95)

    @property
    def p99_ms(self) -> float:
        return self.percentile(99)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "rps": round(self.rps, 1),
            "avg_ms": round(self.avg_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
            "p99_ms": round(self.p99_ms, 4),
            "total_seconds": round(self.total_seconds, 4),
        }


async def bench_async(name: str, func: Callable, iterations: int = 1000) -> BenchResult:
    """اجرای تابع async و اندازهگیری تأخیر هر فراخوانی."""
    latencies: list[float] = []
    start = time.perf_counter()

    for _ in range(iterations):
        t0 = time.perf_counter()
        await func()
        latencies.append((time.perf_counter() - t0) * 1000)

    total = time.perf_counter() - start
    return BenchResult(name, iterations, total, latencies)


def bench_sync(name: str, func: Callable, iterations: int = 1000) -> BenchResult:
    """اجرای تابع sync و اندازهگیری تأخیر هر فراخوانی."""
    latencies: list[float] = []
    start = time.perf_counter()

    for _ in range(iterations):
        t0 = time.perf_counter()
        func()
        latencies.append((time.perf_counter() - t0) * 1000)

    total = time.perf_counter() - start
    return BenchResult(name, iterations, total, latencies)


async def run_all() -> dict[str, Any]:
    from badking.filters.magic import F
    from badking.utils import smart_split_text, to_english_digits
    from badking.hybrid.proto import build, decode

    results: list[BenchResult] = []

    # ۱. Magic Filter
    text_filter = F.text == "/start"
    results.append(await bench_async("filter.text_eq", lambda: _noop(text_filter, "x")))

    # ۲. تبدیل ارقام فارسی
    results.append(
        bench_sync("digits.fa_to_en", lambda: to_english_digits("۱۲۳۴۵۶۷۸۹۰"))
    )

    # ۳. برش متن بلند
    long_text = "لورم ایپسوم " * 1000
    results.append(bench_sync("text.smart_split", lambda: smart_split_text(long_text)))

    # ۴. protobuf encode/decode
    def proto_roundtrip():
        payload = build({1: "سلام", 2: 123})
        return decode(payload)

    results.append(bench_sync("proto.roundtrip", proto_roundtrip, iterations=500))

    return {
        "version": "0.2.0",
        "python": _python_version(),
        "results": [r.to_dict() for r in results],
        "note": "اعداد مربوط به این ماشیناند. ادعای مقایسه با aiobale بدون benchmark یکسان معتبر نیست.",
    }


async def _noop(filter_obj, value):
    """برای اندازهگیری خالص filter."""
    return bool(filter_obj(value))


def _python_version() -> str:
    import platform

    return platform.python_version()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="BADKING benchmark")
    parser.add_argument("--json", action="store_true", help="خروجی JSON")
    args = parser.parse_args()

    data = asyncio.run(run_all())

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    print(f"BADKING Benchmark — Python {data['python']}")
    print(f"{'name':<24} {'RPS':>10} {'avg ms':>10} {'p95 ms':>10} {'p99 ms':>10}")
    print("-" * 68)
    for r in data["results"]:
        print(
            f"{r['name']:<24} {r['rps']:>10.1f} {r['avg_ms']:>10.4f} "
            f"{r['p95_ms']:>10.4f} {r['p99_ms']:>10.4f}"
        )
    print()
    print(data["note"])


if __name__ == "__main__":
    main()
