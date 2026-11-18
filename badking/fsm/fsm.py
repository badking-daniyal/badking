"""FSM — ماشین 상태 مکالمه (قویتر از aiobale: timeout، nested data، migration)."""

from __future__ import annotations

import time
from typing import Any


class State:
    def __init__(self, name: str = ""):
        self.name = name

    def __set_name__(self, owner: type, name: str) -> None:
        if not self.name:
            self.name = f"{owner.__name__}.{name}"

    def __repr__(self) -> str:
        return f"State({self.name})"


class StatesGroupMeta(type):
    def __new__(mcs, name, bases, ns):
        # stateهای والد را هم به ارث ببر (به ترتیب MRO)، سپس stateهای جدید را اضافه کن
        states: dict[str, State] = {}
        for base in bases:
            states.update(getattr(base, "__states__", {}))
        states.update({k: v for k, v in ns.items() if isinstance(v, State)})
        cls = super().__new__(mcs, name, bases, ns)
        cls.__states__ = states
        return cls


class StatesGroup(metaclass=StatesGroupMeta):
    __states__: dict[str, State] = {}

    @classmethod
    def all(cls) -> list[State]:
        return list(cls.__states__.values())


class FSMContext:
    """وضعیت یک کاربر/چت: state + data + timestamp."""

    def __init__(self, storage: Any, key: str):
        self.storage = storage
        self.key = str(key)

    async def set_state(self, state: State | str | None) -> None:
        name = state.name if isinstance(state, State) else state
        record = await self.storage.get(self.key) or {}
        record["state"] = name
        record["updated_at"] = time.time()
        await self.storage.set(self.key, record)

    async def get_state(self) -> str | None:
        record = await self.storage.get(self.key) or {}
        return record.get("state")

    async def update_data(self, **kwargs: Any) -> None:
        record = await self.storage.get(self.key) or {}
        data = record.setdefault("data", {})
        data.update(kwargs)
        record["updated_at"] = time.time()
        await self.storage.set(self.key, record)

    async def get_data(self) -> dict[str, Any]:
        record = await self.storage.get(self.key) or {}
        return dict(record.get("data", {}))

    async def clear(self) -> None:
        await self.storage.delete(self.key)

    async def is_expired(self, timeout_seconds: float) -> bool:
        record = await self.storage.get(self.key) or {}
        updated = record.get("updated_at", 0)
        return bool(updated) and (time.time() - updated) > timeout_seconds

    async def migrate(self, mapping: dict[str, str]) -> None:
        """مهاجرت حالت وقتی جریان ربات عوض میشود."""
        record = await self.storage.get(self.key) or {}
        old = record.get("state")
        if old in mapping:
            record["state"] = mapping[old]
            record["updated_at"] = time.time()
            await self.storage.set(self.key, record)
