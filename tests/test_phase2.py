"""تستهای فاز ۲: FSM، Storage، RateLimiter، OffsetStore."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking.fsm import FSMContext, State, StatesGroup  # noqa: E402
from badking.ratelimit import RateLimiter  # noqa: E402
from badking.recovery import OffsetStore  # noqa: E402
from badking.storage import MemoryStorage, SQLiteStorage  # noqa: E402


class OrderForm(StatesGroup):
    item = State()
    address = State()


@pytest.mark.asyncio
async def test_fsm_memory():
    storage = MemoryStorage()
    ctx = FSMContext(storage, "123:456")
    await ctx.set_state(OrderForm.item)
    await ctx.update_data(item="کتاب")
    assert await ctx.get_state() == "OrderForm.item"
    assert (await ctx.get_data())["item"] == "کتاب"
    await ctx.clear()
    assert await ctx.get_state() is None


@pytest.mark.asyncio
async def test_fsm_migration():
    storage = MemoryStorage()
    ctx = FSMContext(storage, "1:1")
    await ctx.set_state("OldForm.name")
    await ctx.migrate({"OldForm.name": "NewForm.full_name"})
    assert await ctx.get_state() == "NewForm.full_name"


@pytest.mark.asyncio
async def test_fsm_sqlite(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "fsm.db"))
    ctx = FSMContext(storage, "u1")
    await ctx.set_state(OrderForm.address)
    await ctx.update_data(address="تهران")
    ctx2 = FSMContext(SQLiteStorage(str(tmp_path / "fsm.db")), "u1")
    assert await ctx2.get_state() == "OrderForm.address"
    assert (await ctx2.get_data())["address"] == "تهران"


@pytest.mark.asyncio
async def test_fsm_timeout():
    storage = MemoryStorage()
    ctx = FSMContext(storage, "1")
    await ctx.set_state(OrderForm.item)
    assert not await ctx.is_expired(timeout_seconds=100)

    # روی ویندوز دقت time.time() حدود ۱۵.۶ میلی‌ثانیه است، پس
    # sleep(0.01) ممکن است هیچ تغییری در timestamp ایجاد نکند.
    # شرط را می‌پاییم، نه زمان را.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if await ctx.is_expired(timeout_seconds=0.001):
            break
        await asyncio.sleep(0.01)
    assert await ctx.is_expired(timeout_seconds=0.001)


@pytest.mark.asyncio
async def test_rate_limiter_priority():
    limiter = RateLimiter(rate=1000, burst=1000)
    order = []

    async def make_task(name):
        async def job():
            order.append(name)
        return await limiter.submit(job, priority=1 if name == "high" else 0)

    await asyncio.gather(make_task("low"), make_task("high"))
    assert order[0] == "high"


@pytest.mark.asyncio
async def test_rate_limiter_penalty():
    limiter = RateLimiter(rate=1000, burst=10)
    limiter.penalize(retry_after=0.05)
    assert limiter.penalty_until > 0
    assert limiter._tokens == 0


def test_offset_store(tmp_path):
    store = OffsetStore(str(tmp_path / "offset.json"))
    assert store.load() == 0
    store.save(42)
    assert store.load() == 42
    store.reset()
    assert store.load() == 0
