"""مقایسه مستقیم BADKING و aiobale — ورودی flat که هر دو میپذیرند.

aiobale ProtoBuf.encode() از کلید رشتهیی فیلدها استفاده میکند و dict تودرتو
با کلید عددی را نمیپذیرد. بنابراین برای مقایسه منصفانه فقط فیلدهای ساده
(int/str/bytes/bool) را میسنجیم.
"""

from __future__ import annotations

import gc
import json
import statistics
import time
import tracemalloc

WARMUP = 1000
ROUNDS = 7
ITERATIONS = 5000


def p95(v):
    o = sorted(v)
    return o[min(len(o) - 1, int(len(o) * 0.95))]


def bench(fn):
    for _ in range(WARMUP):
        fn()
    gc.collect()
    per = []
    for _ in range(ROUNDS):
        t0 = time.perf_counter()
        for _ in range(ITERATIONS):
            fn()
        per.append((time.perf_counter() - t0) * 1000 / ITERATIONS)
    return {
        "median_ms": round(statistics.median(per), 6),
        "p95_ms": round(p95(per), 6),
        "stddev_ms": round(statistics.stdev(per), 6),
    }


def mem(fn, n=2000):
    gc.collect()
    tracemalloc.start()
    for _ in range(n):
        fn()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return round(peak / 1024, 2)


def main():
    from badking.hybrid.proto import build
    from aiobale.utils.protobuf import ProtoBuf

    pb = ProtoBuf()
    cases = {
        "small": ({1: 42, 2: "hi"}, {"1": 42, "2": "hi"}),
        "medium": ({1: 42, 2: "سلام دنیا", 3: 123456, 4: True, 5: 999999},
                   {"1": 42, "2": "سلام دنیا", "3": 123456, "4": True, "5": 999999}),
        "large": ({1: "متن طولانی" * 200, 2: list(range(100))},
                  {"1": "متن طولانی" * 200, "2": list(range(100))}),
        "boundary": ({1: 0, 2: 127, 3: 128, 4: 2**63 - 1, 5: -1, 6: ""},
                     {"1": 0, "2": 127, "3": 128, "4": 2**63 - 1, "5": -1, "6": ""}),
    }

    out = {}
    for name, (bk, aio) in cases.items():
        out[name] = {
            "badking": bench(lambda p=bk: build(p)),
            "aiobale": bench(lambda p=aio: pb.encode(p)),
            "badking_peak_kb": mem(lambda p=bk: build(p)),
            "aiobale_peak_kb": mem(lambda p=aio: pb.encode(p)),
        }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
