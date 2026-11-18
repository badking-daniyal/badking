"""Audit Log — مشخص باشد کی چی عوض کرد (برای پنل ادمین و RBAC)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AuditEntry:
    timestamp: float
    actor: str
    action: str
    target: str
    details: dict[str, Any]


class AuditLog:
    def __init__(self, path: str | None = None):
        self.path = Path(path) if path else None
        self._entries: list[AuditEntry] = []
        # بارگذاری سوابق قبلی هنگام راهاندازی مجدد
        if self.path and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    self._entries.append(AuditEntry(
                        timestamp=d.get("timestamp", 0),
                        actor=d.get("actor", ""),
                        action=d.get("action", ""),
                        target=d.get("target", ""),
                        details=d.get("details", {}),
                    ))
                except (ValueError, TypeError):
                    continue

    def record(self, actor: str, action: str, target: str = "", **details: Any) -> AuditEntry:
        entry = AuditEntry(time.time(), actor, action, target, details)
        self._entries.append(entry)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return entry

    def list(self, actor: str | None = None, limit: int = 100) -> list[AuditEntry]:
        if limit <= 0:
            return []
        entries = self._entries
        if actor:
            entries = [e for e in entries if e.actor == actor]
        return list(entries[-limit:])


class RBAC:
    """دسترسی مبتنی بر نقش ساده."""

    def __init__(self):
        self._roles: dict[str, set[str]] = {}

    def grant(self, role: str, permission: str) -> None:
        self._roles.setdefault(role, set()).add(permission)

    def has(self, role: str, permission: str) -> bool:
        return permission in self._roles.get(role, set())
