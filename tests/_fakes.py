"""کلاینت‌های تقلبی برای تست Redis و Postgres بدون سرور واقعی.

چرا: تستی که به سرور واقعی وصل می‌شود، روی CI می‌شکند و کند است. این
فایل رفتار لازم را شبیه‌سازی می‌کند — همان متدهایی که کد ما صدا می‌زند.
"""

from __future__ import annotations

import json
import time
from typing import Any


class FakeRedis:
    """شبیه‌ساز حداقلی redis.asyncio برای تست.

    فقط متدهایی را دارد که RedisStorage استفاده می‌کند:
    get, set, delete, keys, exists, ttl, ping, aclose
    """

    def __init__(self) -> None:
        self.data: dict[str, tuple[str, float | None]] = {}
        self.closed = False
        self.fail_on: set[str] = set()

    def _check(self, op: str) -> None:
        if op in self.fail_on:
            raise ConnectionError(f"شبیه‌سازی خطای {op}")

    def _expired(self, key: str) -> bool:
        entry = self.data.get(key)
        if not entry:
            return True
        _, expires = entry
        return expires is not None and time.monotonic() > expires

    async def get(self, key: str) -> str | None:
        self._check("get")
        if self._expired(key):
            self.data.pop(key, None)
            return None
        return self.data[key][0]

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._check("set")
        expires = time.monotonic() + ex if ex else None
        self.data[key] = (value, expires)
        return True

    async def delete(self, *keys: str) -> int:
        self._check("delete")
        removed = 0
        for key in keys:
            if self.data.pop(key, None) is not None:
                removed += 1
        return removed

    async def keys(self, pattern: str = "*") -> list[str]:
        self._check("keys")
        prefix = pattern.rstrip("*")
        return [k for k in self.data if k.startswith(prefix) and not self._expired(k)]

    async def exists(self, key: str) -> int:
        self._check("exists")
        return 0 if self._expired(key) else 1

    async def ttl(self, key: str) -> int:
        self._check("ttl")
        entry = self.data.get(key)
        if not entry:
            return -2
        _, expires = entry
        if expires is None:
            return -1
        left = int(expires - time.monotonic())
        return max(0, left)

    async def ping(self) -> bool:
        self._check("ping")
        return True

    async def aclose(self) -> None:
        self.closed = True


class FakeRecord(dict):
    """یک ردیف asyncpg: هم با ["key"] و هم با .get کار می‌کند."""


class FakeConnection:
    """شبیه‌ساز asyncpg.Connection برای تست."""

    def __init__(self, store: "FakePostgres") -> None:
        self.store = store

    async def execute(self, sql: str, *args: Any) -> str:
        self.store.queries.append(sql)
        upper = sql.strip().upper()
        table = self.store.table

        if upper.startswith("CREATE"):
            return "CREATE TABLE"

        if upper.startswith("INSERT"):
            key, payload = args[0], args[1]
            self.store.rows[key] = (json.loads(payload), time.monotonic())
            return "INSERT 0 1"

        if upper.startswith("DELETE"):
            if "WHERE key = $1" in sql:
                self.store.rows.pop(args[0], None)
                return "DELETE 1"
            if "updated_at <=" in sql:
                cutoff = time.monotonic() - self.store.ttl if self.store.ttl else 0
                gone = [k for k, (_, ts) in self.store.rows.items() if ts <= cutoff]
                for key in gone:
                    self.store.rows.pop(key, None)
                return f"DELETE {len(gone)}"
            count = len(self.store.rows)
            self.store.rows.clear()
            return f"DELETE {count}"

        return "OK"

    async def fetchrow(self, sql: str, *args: Any) -> FakeRecord | None:
        self.store.queries.append(sql)
        key = args[0]
        entry = self.store.rows.get(key)
        if entry is None:
            return None
        value, ts = entry
        if self.store.ttl and time.monotonic() - ts > self.store.ttl:
            return None
        return FakeRecord(value=json.dumps(value))

    async def fetch(self, sql: str, *args: Any) -> list[FakeRecord]:
        self.store.queries.append(sql)
        out = []
        for key, (_, ts) in self.store.rows.items():
            if self.store.ttl and time.monotonic() - ts > self.store.ttl:
                continue
            out.append(FakeRecord(key=key))
        return out

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.store.queries.append(sql)
        if "SELECT 1" in sql and "COUNT" not in sql:
            if "WHERE key = $1" in sql:
                return 1 if args[0] in self.store.rows else None
            return 1
        if "COUNT(*)" in sql:
            return len(self.store.rows)
        return None


class _Acquire:
    """context manager برای pool.acquire()."""

    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self.conn

    async def __aexit__(self, *exc: Any) -> None:
        return None


class FakePool:
    """شبیه‌ساز asyncpg.Pool."""

    def __init__(self, store: "FakePostgres") -> None:
        self.store = store
        self.conn = FakeConnection(store)
        self.closed = False

    def acquire(self) -> _Acquire:
        return _Acquire(self.conn)

    async def close(self) -> None:
        self.closed = True


class FakePostgres:
    """وضعیت مشترک بین Pool و Connection."""

    def __init__(self, table: str = "badking_fsm", ttl: int | None = None) -> None:
        self.table = table
        self.ttl = ttl
        self.rows: dict[str, tuple[dict[str, Any], float]] = {}
        self.queries: list[str] = []
        self.pool = FakePool(self)
