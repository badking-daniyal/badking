"""PostgreSQLStorage — وضعیت FSM روی Postgres.

    from badking.storage import PostgreSQLStorage

    storage = PostgreSQLStorage("postgresql://user:pass@localhost/badking")

نیاز به `asyncpg` دارد:  pip install asyncpg

چرا Postgres و نه فقط Redis: Redis سریع است ولی حافظه‌اش محدود و
پایدار نیست. اگر مکالمه باید ماه‌ها بماند و بتوانی روی آن کوئری بزنی،
Postgres جواب است.

جدول خودش ساخته می‌شود. اگر از قبل جدولی با نام دیگر داری، `table`
را عوض کن.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger("badking.storage.postgres")

# نام جدول با حرف شروع می‌شود و فقط حرف و رقم و آندرلاین دارد.
# این را چک می‌کنیم چون نام جدول را نمی‌شود پارامتر کرد و باید در
# متن SQL درج شود — بدون چک، در باز است برای SQL Injection.
import re

_SAFE_TABLE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class PostgreSQLStorageError(Exception):
    """خطای Postgres، با راهنمای رفع."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message}\n  → {self.hint}" if self.hint else self.message


class PostgreSQLStorage:
    """وضعیت‌ها در یک جدول Postgres.

    Args:
        dsn: رشته اتصال. مثال: ``postgresql://user:pass@host/db``
        table: نام جدول. پیش‌فرض ``badking_fsm``.
        ttl: ثانیه تا انقضای خودکار. ``None`` یعنی بدون انقضا.
        pool_size: اندازه Connection Pool.
        pool: یک asyncpg.Pool آماده. اگر بدهی، ``dsn`` نادیده گرفته می‌شود.
    """

    def __init__(
        self,
        dsn: str = "postgresql://postgres@localhost/badking",
        *,
        table: str = "badking_fsm",
        ttl: int | None = None,
        pool_size: int = 5,
        pool: Any = None,
    ) -> None:
        if not _SAFE_TABLE.match(table):
            raise PostgreSQLStorageError(
                f"نام جدول نامعتبر: {table!r}",
                hint="فقط حرف کوچک، رقم و آندرلاین. باید با حرف شروع شود.",
            )

        self.dsn = dsn
        self.table = table
        self.ttl = ttl
        self.pool_size = pool_size
        self._pool = pool
        self._owned = pool is None

    # ---------- اتصال ----------

    async def connect(self) -> None:
        """اتصال و ساخت جدول."""
        if self._pool is not None:
            return

        try:
            import asyncpg
        except ImportError as exc:
            raise PostgreSQLStorageError(
                "پکیج asyncpg نصب نیست",
                hint="pip install asyncpg   (یا: pip install badking[postgres])",
            ) from exc

        try:
            self._pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=self.pool_size)
        except Exception as exc:  # noqa: BLE001
            raise PostgreSQLStorageError(
                f"اتصال به Postgres نشد: {exc}",
                hint="dsn را چک کن. سرویس Postgres روشن است؟ رمز درست است؟",
            ) from exc

        await self._create_table()
        log.debug("اتصال Postgres: %s (جدول %s)", self.dsn, self.table)

    async def _create_table(self) -> None:
        pool = self._pool
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    key        TEXT PRIMARY KEY,
                    value      JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            if self.ttl:
                # ایندکس روی updated_at تا پاک‌سازی منقضی‌ها سریع باشد
                await conn.execute(
                    f"CREATE INDEX IF NOT EXISTS {self.table}_updated_idx "
                    f"ON {self.table} (updated_at)"
                )

    async def close(self) -> None:
        """بستن Pool. فقط اگر خودمان ساخته باشیم."""
        if self._pool is not None and self._owned:
            await self._pool.close()
            self._pool = None

    async def _get_pool(self) -> Any:
        if self._pool is None:
            await self.connect()
        return self._pool

    def _fresh_sql(self, alias: str = "") -> str:
        """شرط «منقضی نشده» — اگر TTL نداشته باشیم، همیشه درست است."""
        if not self.ttl:
            return ""
        col = f"{alias}.updated_at" if alias else "updated_at"
        return f" AND {col} > NOW() - INTERVAL '{int(self.ttl)} seconds'"

    # ---------- رابط Storage ----------

    async def get(self, key: str) -> dict[str, Any] | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT value FROM {self.table} WHERE key = $1{self._fresh_sql()}",
                key,
            )

        if row is None:
            return None

        value = row["value"]
        # asyncpg برای JSONB رشته می‌دهد، مگر codec تنظیم شده باشد
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                log.warning("مقدار خراب در Postgres برای کلید %s — پاک شد", key)
                await self.delete(key)
                return None

        return value if isinstance(value, dict) else None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        pool = await self._get_pool()
        payload = json.dumps(value, ensure_ascii=False)
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {self.table} (key, value, updated_at)
                VALUES ($1, $2::jsonb, NOW())
                ON CONFLICT (key) DO UPDATE
                   SET value = EXCLUDED.value, updated_at = NOW()
                """,
                key,
                payload,
            )

    async def delete(self, key: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"DELETE FROM {self.table} WHERE key = $1", key)

    async def keys(self) -> list[str]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT key FROM {self.table} WHERE TRUE{self._fresh_sql()}"
            )
        return [r["key"] for r in rows]

    # ---------- افزوده‌ها ----------

    async def exists(self, key: str) -> bool:
        """آیا این کلید هست؟"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchval(
                f"SELECT 1 FROM {self.table} WHERE key = $1{self._fresh_sql()}",
                key,
            )
        return row is not None

    async def count(self) -> int:
        """چند وضعیت فعال هست؟"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return int(
                await conn.fetchval(
                    f"SELECT COUNT(*) FROM {self.table} WHERE TRUE{self._fresh_sql()}"
                )
            )

    async def purge_expired(self) -> int:
        """رکوردهای منقضی را پاک می‌کند. تعداد را برمی‌گرداند.

        اگر TTL نداشته باشی، هیچ کاری نمی‌کند و 0 برمی‌گرداند.
        """
        if not self.ttl:
            return 0

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {self.table} "
                f"WHERE updated_at <= NOW() - INTERVAL '{int(self.ttl)} seconds'"
            )
        # asyncpg برمی‌گرداند: "DELETE 3"
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0

    async def clear(self) -> int:
        """همه رکوردهای این جدول را پاک می‌کند."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(f"DELETE FROM {self.table}")
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0

    async def health(self) -> bool:
        """آیا Postgres جواب می‌دهد؟"""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                return await conn.fetchval("SELECT 1") == 1
        except Exception as exc:  # noqa: BLE001
            log.warning("سلامت Postgres: %s", exc)
            return False

    def __repr__(self) -> str:
        ttl = f", ttl={self.ttl}" if self.ttl else ""
        return f"<PostgreSQLStorage {self.table}{ttl}>"
