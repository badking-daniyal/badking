"""ORM سبک — ذخیره هر نوع داده بدون تنظیمات اضافی (SQLite-backed key/value + جدول)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Store:
    """جدول ساده با رابط شبیه ORM: insert/find/update/delete."""

    def __init__(self, path: str = "badking_data.db", table: str = "records"):
        # جلوگیری از تزریق SQL از طریق نام جدول
        if not _TABLE_RE.match(table):
            raise ValueError("نام جدول نامعتبر است (فقط حروف، اعداد و _ مجازاند)")
        self.path = Path(path)
        self.table = table
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self):
        import sqlite3
        conn = sqlite3.connect(str(self.path))
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {self.table} "
            "(id TEXT PRIMARY KEY, data TEXT, kind TEXT)"
        )
        conn.commit()
        return conn

    def _init(self) -> None:
        self._conn().close()

    def put(self, id: str, data: dict[str, Any], kind: str = "default") -> None:
        conn = self._conn()
        conn.execute(
            f"INSERT OR REPLACE INTO {self.table} (id,data,kind) VALUES (?,?,?)",
            (str(id), json.dumps(data, ensure_ascii=False, default=str), kind),
        )
        conn.commit()
        conn.close()

    def get(self, id: str) -> dict[str, Any] | None:
        conn = self._conn()
        row = conn.execute(f"SELECT data FROM {self.table} WHERE id=?", (str(id),)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None

    def find(self, kind: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._conn()
        if kind:
            rows = conn.execute(
                f"SELECT data FROM {self.table} WHERE kind=? LIMIT ?", (kind, limit)
            ).fetchall()
        else:
            rows = conn.execute(f"SELECT data FROM {self.table} LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]

    def delete(self, id: str) -> None:
        conn = self._conn()
        conn.execute(f"DELETE FROM {self.table} WHERE id=?", (str(id),))
        conn.commit()
        conn.close()
