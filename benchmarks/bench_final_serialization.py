"""FINAL Serialization Benchmark — شرایط کنترلشده و قابل تکرار.

روش:
- 1000 warm-up
- 7 اجرای مستقل × 5000 تکرار
- median / P95 / stddev / memory (tracemalloc)
- ورودی: small / medium / large / boundary
- مقایسه BADKING و aiobale با همان ساختار فیلدها
- ثبت Python version و platform

استفاده:
    python benchmarks/bench_final_serialization.py
    # با aiobale در PYTHONPATH:
    PYTHONPATH=/path/to/aiobale python benchmarks/bench_final_serialization.py
"""

from __future__ import annotations

import gc
import json
import platform
import statistics
import sys
import time
import tracemalloc


WARMUP = 1000
ROUNDS = 7
ITERATIONS = 5000


def p95(values):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]


def bench(fn):
    for _ in range(WARMUP):
        fn()
    gc.collect()
    per_round = []
    for _ in range(ROUNDS):
        t0 = time.perf_counter()
        for _ in range(ITERATIONS):
            fn()
        per_round.append((time.perf_counter() - t0) * 1000 / ITERATIONS)
    return {
        "median_ms": round(statistics.median(per_round), 6),
        "p95_ms": round(p95(per_round), 6),
        "stddev_ms": round(statistics.stdev(per_round), 6) if len(per_round) > 1 else 0.0,
        "min_ms": round(min(per_round), 6),
    }


def memory(fn, iterations=2000):
    gc.collect()
    tracemalloc.start()
    for _ in range(iterations):
        fn()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "current_kb": round(current / 1024, 2),
        "peak_kb": round(peak / 1024, 2),
    }


def inputs():
    """چهار اندازه ورودی — همان ساختار فیلدها."""
    return {
        "small": {1: 42, 2: "hi"},
        "medium": {1: 42, 2: "سلام دنیا", 3: 123456, 4: {1: 7, 2: "x"}, 5: [1, 2, 3]},
        "large": {1: 42, 2: "متن طولانی" * 200, 3: list(range(100)), 4: {1: "a" * 500}},
        "boundary": {
            1: 0,                      # صفر
            2: 127,                    # مرز varint ۱ بایته
            3: 128,                    # مرز varint ۲ بایته
            4: 2**63 - 1,              # حداکثر int64
            5: -1,                     # منفی
            6: "",                     # رشته خالی
            7: b"",                    # بایت خالی
            8: True,                   # bool
        },
    }


def main():
    from badking.hybrid.proto import build

    result = {
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "method": {
            "warmup": WARMUP,
            "rounds": ROUNDS,
            "iterations_per_round": ITERATIONS,
            "metrics": "median/P95/stddev of per-round mean, tracemalloc peak",
        },
        "badking": {},
        "aiobale": {},
    }

    for name, payload in inputs().items():
        result["badking"][name] = bench(lambda p=payload: build(p))
        result["badking"][name]["memory"] = memory(lambda p=payload: build(p))

    try:
        from aiobale.utils.protobuf import ProtoBuf

        pb = ProtoBuf()
        # همان فیلدها با کلید رشتهیی (قرارداد aiobale)
        for name, payload in inputs().items():
            aio = {str(k): v for k, v in payload.items()}
            result["aiobale"][name] = bench(lambda p=aio: pb.encode(p))
            result["aiobale"][name]["memory"] = memory(lambda p=aio: pb.encode(p))
    except Exception as exc:
        result["aiobale"] = {"error": f"{type(exc).__name__}: {str(exc)[:150]}"}

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
