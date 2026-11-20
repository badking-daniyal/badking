"""Reproducible benchmark for BADKING Session Storage.

Run:
    python benchmarks/bench_session.py

Reports median/min/max over repeated runs with warm-up. Environment
(Python version, platform, cryptography version) is printed for traceability.
No real credentials are used — all data is synthetic.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking.hybrid.session import (  # noqa: E402
    MAGIC_V1,
    MODE_XOR_HMAC,
    PBKDF2_ROUNDS,
    Session,
    SessionStore,
    _derive_key,
    _xor_stream,
)

WARMUP = 3
RUNS = 9
PW = "benchmark-password-not-a-real-secret"


def bench(fn, runs=RUNS, warmup=WARMUP):
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1000.0)
    return statistics.median(samples), min(samples), max(samples)


def show(label, triple):
    med, lo, hi = triple
    print(f"  {label:<42} median={med:8.3f} ms  min={lo:8.3f}  max={hi:8.3f}")


def main():
    print("=== Environment ===")
    print(f"  Python       : {platform.python_version()}")
    print(f"  Platform     : {platform.platform()}")
    try:
        import cryptography
        print(f"  cryptography : {cryptography.__version__}")
    except ImportError:
        print("  cryptography : NOT INSTALLED")
    print(f"  PBKDF2_ROUNDS: {PBKDF2_ROUNDS}")
    print()

    salt = os.urandom(16)
    pw = PW.encode()

    print("=== PBKDF2-HMAC-SHA256 (key derivation) ===")
    for rounds in (200_000, 310_000, 600_000, 1_000_000):
        show(
            f"pbkdf2 rounds={rounds}",
            bench(lambda r=rounds: hashlib.pbkdf2_hmac("sha256", pw, salt, r, dklen=32)),
        )
    print()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        p = td / "s.session"
        store = SessionStore(p, password=PW)
        sess = Session(access_token="synthetic.jwt.token", user_id=1, phone="1000")

        print("=== Encrypt / Decrypt (BKS2) ===")
        blob = store._encrypt(json.dumps({"sessions": {}}).encode())
        show("encrypt small payload", bench(lambda: store._encrypt(b'{"sessions":{}}')))
        show("decrypt small payload", bench(lambda: store._decrypt(blob)))
        big = json.dumps({"sessions": {f"user:{i}": sess.to_dict() for i in range(50)}}).encode()
        show("encrypt 50-account payload", bench(lambda: store._encrypt(big)))
        big_blob = store._encrypt(big)
        show("decrypt 50-account payload", bench(lambda: store._decrypt(big_blob)))
        print()

        print("=== Save / Load ===")
        sessions = {f"user:{i}": Session(access_token="t" * 40, user_id=i) for i in range(10)}
        show("save_all (10 accounts)", bench(lambda: store.save_all(sessions)))
        show("load_all (10 accounts)", bench(lambda: store.load_all()))
        print()

        print("=== Migration BKS1 -> BKS2 ===")

        def fresh_legacy():
            q = td / f"m_{os.urandom(4).hex()}.session"
            payload = json.dumps({"version": 1, "sessions": {"user:1": {"access_token": "x", "user_id": 1}}}).encode()
            s = os.urandom(16)
            key = _derive_key(PW, s)
            body = _xor_stream(payload, key)
            mac = hmac.new(key, body, hashlib.sha256).digest()
            q.write_bytes(MAGIC_V1 + MODE_XOR_HMAC + s + mac + body)
            return q

        def do_migrate():
            q = fresh_legacy()
            SessionStore(q, password=PW).migrate_to_v2(backup=False)

        show("migrate BKS1->BKS2 (no backup)", bench(do_migrate))
        print()

    print("Done. All inputs synthetic; no real session or credential used.")


if __name__ == "__main__":
    import hmac  # noqa: E402

    main()
