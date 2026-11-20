"""Serialization benchmark — قابل تکرار، با warm-up و ورودی یکسان.

روش:
- 500 warm-up (برای گرم کردن cache و JIT-مانند رفتار CPython)
- 3000 تکرار، 5 دور جداگانه
- گزارش median / P95 / P99 / memory (tracemalloc)
- مقایسه BADKING در برابر aiobale با همان ساختار ورودی

استفاده:
    python benchmarks/bench_serialization.py
"""

from __future__ import annotations

import gc
import json
import statistics
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WARMUP = 500
ROUNDS = 5
ITERATIONS = 3000


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(len(ordered) * p))
    return ordered[idx]


def bench_call(fn, *, warmup=WARMUP, rounds=ROUNDS, iterations=ITERATIONS):
    """زمان هر فراخوانی را بر حسب میلیثانیه میسنجد."""
    for _ in range(warmup):
        fn()
    gc.collect()
    per_round = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        for _ in range(iterations):
            fn()
        elapsed = (time.perf_counter() - t0) * 1000
        per_round.append(elapsed / iterations)
    return {
        "median_ms": round(statistics.median(per_round), 6),
        "p95_ms": round(percentile(per_round, 0.95), 6),
        "p99_ms": round(percentile(per_round, 0.99), 6),
        "min_ms": round(min(per_round), 6),
        "rounds": rounds,
        "iterations_per_round": iterations,
        "warmup": warmup,
    }


def bench_memory(fn, iterations=1000):
    gc.collect()
    tracemalloc.start()
    for _ in range(iterations):
        fn()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "current_kb": round(current / 1024, 2),
        "peak_kb": round(peak / 1024, 2),
        "iterations": iterations,
    }


def main():
    from badking.hybrid.proto import build, encode_named

    results = {}

    # ورودی یکسان: SendMessage peer{type,id,accessHash} + message_id + content
    simple = {1: 42, 2: 123456, 3: "سلام دنیا", 6: 7}
    schema = {
        "peer": {"field": 1, "fields": {"type": 1, "id": 2, "accessHash": 3}},
        "message_id": 2,
        "content": {"field": 3, "fields": {"text": {"field": 15, "fields": {"value": 1}}}},
    }
    named = {
        "peer": {"type": 1, "id": 42, "accessHash": 0},
        "message_id": 123456,
        "content": {"text": {"value": "سلام دنیا"}},
    }

    results["badking_build"] = bench_call(lambda: build(simple))
    results["badking_encode_named"] = bench_call(lambda: encode_named(named, schema))
    results["badking_build_memory"] = bench_memory(lambda: build(simple))
    results["badking_encode_named_memory"] = bench_memory(lambda: encode_named(named, schema))

    # aiobale — همان ساختار با ProtoBuf().encode
    try:
        from aiobale.utils.protobuf import ProtoBuf

        pb = ProtoBuf()
        # همان فیلدها با کلید رشتهیی alias
        aio_data = {"1": 42, "2": 123456, "3": "سلام دنیا", "6": 7}
        results["aiobale_serialize"] = bench_call(lambda: pb.encode(aio_data))
        results["aiobale_serialize_memory"] = bench_memory(lambda: pb.encode(aio_data))
    except Exception as exc:
        results["aiobale_serialize"] = {
            "error": f"{type(exc).__name__}: {str(exc)[:120]}"
        }

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
