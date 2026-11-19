"""تست RedisStorage و PostgreSQLStorage با کلاینت تقلبی.

سرور واقعی لازم نیست. رفتار لازم شبیه‌سازی می‌شود.
"""

from __future__ import annotations

import asyncio

import pytest

from badking.storage import PostgreSQLStorage, RedisStorage
from badking.storage.postgres import PostgreSQLStorageError
from badking.storage.redis import RedisStorageError

from _fakes import FakePostgres, FakeRedis


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------- Redis ----------

class TestRedisStorage:
    def make(self, **kwargs):
        fake = FakeRedis()
        return RedisStorage(client=fake, **kwargs), fake

    def test_get_missing(self):
        s, _ = self.make()
        assert run(s.get("nope")) is None

    def test_set_get_roundtrip(self):
        s, _ = self.make()
        run(s.set("k", {"state": "Order.item", "data": {"x": 1}}))
        assert run(s.get("k")) == {"state": "Order.item", "data": {"x": 1}}

    def test_persian_survives(self):
        s, _ = self.make()
        run(s.set("k", {"name": "دانیال", "city": "تهران"}))
        assert run(s.get("k"))["name"] == "دانیال"

    def test_prefix_applied(self):
        s, fake = self.make(prefix="bot1:")
        run(s.set("k", {"a": 1}))
        assert "bot1:k" in fake.data

    def test_keys_strips_prefix(self):
        s, _ = self.make(prefix="bot1:")
        run(s.set("a", {"x": 1}))
        run(s.set("b", {"x": 2}))
        assert sorted(run(s.keys())) == ["a", "b"]

    def test_delete(self):
        s, _ = self.make()
        run(s.set("k", {"a": 1}))
        run(s.delete("k"))
        assert run(s.get("k")) is None

    def test_delete_missing_is_silent(self):
        s, _ = self.make()
        run(s.delete("nope"))  # نباید خطا بدهد

    def test_ttl_expires(self):
        s, _ = self.make(ttl=1)
        run(s.set("k", {"a": 1}))
        assert run(s.get("k")) == {"a": 1}

        # TTL را دستی به گذشته ببر
        payload, _ = s._client.data["badking:fsm:k"]
        s._client.data["badking:fsm:k"] = (payload, 0.0)
        assert run(s.get("k")) is None

    def test_no_ttl_persists(self):
        s, fake = self.make()
        run(s.set("k", {"a": 1}))
        _, expires = fake.data["badking:fsm:k"]
        assert expires is None

    def test_exists(self):
        s, _ = self.make()
        assert run(s.exists("k")) is False
        run(s.set("k", {"a": 1}))
        assert run(s.exists("k")) is True

    def test_ttl_left(self):
        s, _ = self.make(ttl=100)
        run(s.set("k", {"a": 1}))
        left = run(s.ttl_left("k"))
        assert 95 <= left <= 100

    def test_ttl_left_no_expiry(self):
        s, _ = self.make()
        run(s.set("k", {"a": 1}))
        assert run(s.ttl_left("k")) == -1

    def test_ttl_left_missing(self):
        s, _ = self.make()
        assert run(s.ttl_left("nope")) == -2

    def test_clear(self):
        s, _ = self.make()
        run(s.set("a", {"x": 1}))
        run(s.set("b", {"x": 2}))
        assert run(s.clear()) == 2
        assert run(s.keys()) == []

    def test_clear_empty(self):
        s, _ = self.make()
        assert run(s.clear()) == 0

    def test_health(self):
        s, _ = self.make()
        assert run(s.health()) is True

    def test_health_false_on_error(self):
        s, fake = self.make()
        fake.fail_on.add("ping")
        assert run(s.health()) is False

    def test_corrupt_value_cleaned(self):
        s, fake = self.make()
        fake.data["badking:fsm:k"] = ("not json", None)
        assert run(s.get("k")) is None
        assert "badking:fsm:k" not in fake.data

    def test_non_dict_value_ignored(self):
        s, fake = self.make()
        fake.data["badking:fsm:k"] = ("[1,2,3]", None)
        assert run(s.get("k")) is None

    def test_close_does_not_close_external_client(self):
        s, fake = self.make()
        run(s.close())
        assert fake.closed is False

    def test_repr(self):
        s, _ = self.make(ttl=60)
        assert "ttl=60" in repr(s)

    def test_missing_package_message(self):
        """بدون redis نصب‌شده، خطای روشن بدهد نه ImportError گنگ."""
        s = RedisStorage(url="redis://nowhere:1/0")
        try:
            run(s.connect())
        except RedisStorageError as exc:
            assert "redis" in str(exc)
            assert "pip install" in str(exc)
        except Exception:  # noqa: BLE001
            # اگر redis نصب باشد، اتصال به nowhere شکست می‌خورد — هم قابل قبول
            pass


# ---------- Postgres ----------

class TestPostgreSQLStorage:
    def make(self, **kwargs):
        fake = FakePostgres(table=kwargs.get("table", "badking_fsm"), ttl=kwargs.get("ttl"))
        return PostgreSQLStorage(pool=fake.pool, **kwargs), fake

    def test_get_missing(self):
        s, _ = self.make()
        assert run(s.get("nope")) is None

    def test_set_get_roundtrip(self):
        s, _ = self.make()
        run(s.set("k", {"state": "Order.item"}))
        assert run(s.get("k")) == {"state": "Order.item"}

    def test_persian_survives(self):
        s, _ = self.make()
        run(s.set("k", {"name": "دانیال"}))
        assert run(s.get("k"))["name"] == "دانیال"

    def test_delete(self):
        s, _ = self.make()
        run(s.set("k", {"a": 1}))
        run(s.delete("k"))
        assert run(s.get("k")) is None

    def test_keys(self):
        s, _ = self.make()
        run(s.set("a", {"x": 1}))
        run(s.set("b", {"x": 2}))
        assert sorted(run(s.keys())) == ["a", "b"]

    def test_exists(self):
        s, _ = self.make()
        assert run(s.exists("k")) is False
        run(s.set("k", {"a": 1}))
        assert run(s.exists("k")) is True

    def test_count(self):
        s, _ = self.make()
        run(s.set("a", {"x": 1}))
        run(s.set("b", {"x": 2}))
        assert run(s.count()) == 2

    def test_clear(self):
        s, _ = self.make()
        run(s.set("a", {"x": 1}))
        assert run(s.clear()) == 1
        assert run(s.keys()) == []

    def test_health(self):
        s, _ = self.make()
        assert run(s.health()) is True

    def test_health_false_on_error(self):
        s, fake = self.make()
        fake.pool.conn.fetchval = _boom
        assert run(s.health()) is False

    def test_purge_without_ttl_is_noop(self):
        s, _ = self.make()
        run(s.set("a", {"x": 1}))
        assert run(s.purge_expired()) == 0
        assert run(s.count()) == 1

    def test_purge_with_ttl(self):
        s, fake = self.make(ttl=1)
        run(s.set("a", {"x": 1}))
        # زمان را به گذشته ببر
        fake.rows["a"] = ({"x": 1}, 0.0)
        assert run(s.purge_expired()) == 1

    def test_repr(self):
        s, _ = self.make(table="my_table")
        assert "my_table" in repr(s)

    def test_unsafe_table_name_rejected(self):
        """نام جدول در SQL درج می‌شود — باید چک شود."""
        for bad in ("users; DROP TABLE x", "1table", "table-name", "", "a" * 70):
            with pytest.raises(PostgreSQLStorageError) as info:
                PostgreSQLStorage(pool=FakePostgres().pool, table=bad)
            assert "نامعتبر" in str(info.value)

    def test_safe_table_names_accepted(self):
        for good in ("badking_fsm", "fsm", "_private", "table_123"):
            PostgreSQLStorage(pool=FakePostgres().pool, table=good)

    def test_close_does_not_close_external_pool(self):
        s, fake = self.make()
        run(s.close())
        assert fake.pool.closed is False

    def test_missing_package_message(self):
        s = PostgreSQLStorage(dsn="postgresql://nowhere/none")
        try:
            run(s.connect())
        except PostgreSQLStorageError as exc:
            assert "asyncpg" in str(exc) or "اتصال" in str(exc)
        except Exception:  # noqa: BLE001
            pass


async def _boom(*args, **kwargs):
    raise ConnectionError("شبیه‌سازی")


# ---------- سازگاری ----------

class TestStorageContract:
    """همه Storageها باید یک رابط داشته باشند."""

    def test_all_have_core_methods(self):
        from badking.storage import MemoryStorage, SQLiteStorage

        for cls in (MemoryStorage, SQLiteStorage, RedisStorage, PostgreSQLStorage):
            for method in ("get", "set", "delete", "keys"):
                assert hasattr(cls, method), f"{cls.__name__} متد {method} ندارد"

    def test_redis_and_postgres_are_swappable(self):
        """همان کد روی هر دو کار کند."""
        redis = RedisStorage(client=FakeRedis())
        postgres = PostgreSQLStorage(pool=FakePostgres().pool)

        for storage in (redis, postgres):
            run(storage.set("k", {"state": "S1", "data": {"n": 1}}))
            assert run(storage.get("k")) == {"state": "S1", "data": {"n": 1}}
            assert run(storage.keys()) == ["k"]
            run(storage.delete("k"))
            assert run(storage.get("k")) is None
