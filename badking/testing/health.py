"""Health Check — وضعیت سرویس ربات."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class HealthStatus:
    status: str
    uptime_seconds: float
    checks: dict[str, bool]

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "checks": self.checks,
        }


class Health:
    def __init__(self):
        self.started_at = time.time()
        self._checks: dict[str, bool] = {}

    def set(self, name: str, ok: bool) -> None:
        self._checks[name] = ok

    def status(self) -> HealthStatus:
        checks = dict(self._checks)
        all_ok = all(checks.values()) if checks else True
        return HealthStatus(
            status="ok" if all_ok else "degraded",
            uptime_seconds=time.time() - self.started_at,
            checks=checks,
        )
