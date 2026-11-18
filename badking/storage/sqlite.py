"""SQLiteStorage — ذخیره پایدار وضعیتها (بدون وابستگی اضافی)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class SQLiteStorage:
    def __init__(self, path: str = "badking_fsm.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._init()

    def _conn(self):
        import sqlite3
        conn = sqlite3.connect(str(self.path))
        conn.execute("CREATE TABLE IF NOT EXISTS fsm (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        return conn

    def _init(self) -> None:
        conn = self._conn()
        conn.close()

    async def get(self, key: str) -> dict[str, Any] | None:
        async with self._lock:
            conn = self._conn()
            row = conn.execute("SELECT value FROM fsm WHERE key=?", (key,)).fetchone()
            conn.close()
            return json.loads(row[0]) if row else None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        async with self._lock:
            conn = self._conn()
            conn.execute(
                "INSERT OR REPLACE INTO fsm (key,value) VALUES (?,?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            conn.commit()
            conn.close()

    async def delete(self, key: str) -> None:
        async with self._lock:
            conn = self._conn()
            conn.execute("DELETE FROM fsm WHERE key=?", (key,))
            conn.commit()
            conn.close()

    async def keys(self) -> list[str]:
        async with self._lock:
            conn = self._conn()
            rows = conn.execute("SELECT key FROM fsm").fetchall()
            conn.close()
            return [r[0] for r in rows]
