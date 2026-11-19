"""RedisStorage — وضعیت FSM روی Redis، با TTL و قفل توزیع‌شده.

    from badking.storage import RedisStorage

    storage = RedisStorage("redis://localhost:6379/0", ttl=3600)

نیاز به `redis` دارد:  pip install redis

چرا Redis: اگر ربات را روی چند سرور اجرا کنی، SQLite جواب نمی‌دهد.
هر سرور فایل خودش را دارد و کاربر وسط مکالمه، وضعیتش را گم می‌کند.
Redis یک منبع مشترک است.

اگر `redis` نصب نباشد، این کلاس موقع ساخت خطای روشن می‌دهد، نه
ImportError گنگ موقع import.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger("badking.storage.redis")

PREFIX = "badking:fsm:"


class RedisStorageError(Exception):
    """خطای Redis، با راهنمای رفع."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message}\n  → {self.hint}" if self.hint else self.message


class RedisStorage:
    """وضعیت‌ها در Redis.

    Args:
        url: آدرس Redis. مثال: ``redis://localhost:6379/0``
        ttl: ثانیه تا انقضای خودکار هر کلید. ``None`` یعنی بدون انقضا.
        prefix: پیشوند کلیدها، تا چند ربات روی یک Redis قاطی نشوند.
        client: کلاینت آماده Redis. اگر بدهی، ``url`` نادیده گرفته می‌شود.
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        *,
        ttl: int | None = None,
        prefix: str = PREFIX,
        client: Any = None,
    ) -> None:
        self.url = url
        self.ttl = ttl
        self.prefix = prefix
        self._client = client
        self._owned = client is None

    # ---------- اتصال ----------

    async def connect(self) -> None:
        """اتصال. اگر کلاینت از بیرون آمده باشد، کاری نمی‌کند."""
        if self._client is not None:
            return

        try:
            import redis.asyncio as redis
        except ImportError as exc:
            raise RedisStorageError(
                "پکیج redis نصب نیست",
                hint="pip install redis   (یا: pip install badking[redis])",
            ) from exc

        self._client = redis.from_url(self.url, decode_responses=True)
        log.debug("اتصال Redis: %s", self.url)

    async def close(self) -> None:
        """بستن اتصال. فقط اگر خودمان ساخته باشیم."""
        if self._client is not None and self._owned:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> Any:
        if self._client is None:
            await self.connect()
        return self._client

    # ---------- کلید ----------

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    # ---------- رابط Storage ----------

    async def get(self, key: str) -> dict[str, Any] | None:
        client = await self._get_client()
        raw = await client.get(self._key(key))
        if raw is None:
            return None

        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("مقدار خراب در Redis برای کلید %s — پاک شد", key)
            await self.delete(key)
            return None

        return value if isinstance(value, dict) else None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        client = await self._get_client()
        payload = json.dumps(value, ensure_ascii=False)
        if self.ttl:
            await client.set(self._key(key), payload, ex=self.ttl)
        else:
            await client.set(self._key(key), payload)

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(self._key(key))

    async def keys(self) -> list[str]:
        client = await self._get_client()
        found = await client.keys(f"{self.prefix}*")
        return [k[len(self.prefix):] for k in found]

    # ---------- افزوده‌ها ----------

    async def exists(self, key: str) -> bool:
        """آیا این کلید هست؟"""
        client = await self._get_client()
        return bool(await client.exists(self._key(key)))

    async def ttl_left(self, key: str) -> int:
        """چند ثانیه تا انقضا. -1 یعنی بدون انقضا، -2 یعنی کلید نیست."""
        client = await self._get_client()
        return int(await client.ttl(self._key(key)))

    async def clear(self) -> int:
        """همه کلیدهای این ربات را پاک می‌کند. تعداد را برمی‌گرداند."""
        client = await self._get_client()
        found = await client.keys(f"{self.prefix}*")
        if not found:
            return 0
        return int(await client.delete(*found))

    async def health(self) -> bool:
        """آیا Redis جواب می‌دهد؟"""
        try:
            client = await self._get_client()
            return bool(await client.ping())
        except Exception as exc:  # noqa: BLE001
            log.warning("سلامت Redis: %s", exc)
            return False

    def __repr__(self) -> str:
        ttl = f", ttl={self.ttl}" if self.ttl else ""
        return f"<RedisStorage {self.url}{ttl}>"
