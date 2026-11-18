"""Observability — لاگ ساختاریافته (JSON) + شمارندههای Prometheus-compatible."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("badking")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


class Metrics:
    """شمارندهها و تایمرهای ساده، قابل صدور به فرمت Prometheus."""

    def __init__(self, prefix: str = "badking"):
        self.prefix = prefix
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _full_name(self, name: str) -> str:
        return f"{self.prefix}_{name}" if self.prefix else name

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = self._key(self._full_name(name), labels)
        with self._lock:
            self._counters[key] += value

    def gauge(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self._gauges[self._key(self._full_name(name), labels)] = value

    def observe(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self._histograms[self._key(self._full_name(name), labels)].append(value)

    @staticmethod
    def _escape(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    @classmethod
    def _key(cls, name: str, labels: dict[str, str]) -> str:
        if not labels:
            return name
        parts = ",".join(f'{k}="{cls._escape(v)}"' for k, v in sorted(labels.items()))
        return f"{name}{{{parts}}}"

    def render(self) -> str:
        """خروجی متنی Prometheus (یک # TYPE در هر نام متریک)."""
        lines: list[str] = []
        declared: set[str] = set()
        with self._lock:
            for key, val in self._counters.items():
                name = key.split("{")[0]
                label_part = key[len(name):]
                if name not in declared:
                    lines.append(f"# TYPE {name} counter")
                    declared.add(name)
                lines.append(f"{name}{label_part} {val}")
            for key, val in self._gauges.items():
                name = key.split("{")[0]
                label_part = key[len(name):]
                if name not in declared:
                    lines.append(f"# TYPE {name} gauge")
                    declared.add(name)
                lines.append(f"{name}{label_part} {val}")
            for key, vals in self._histograms.items():
                if not vals:
                    continue
                name = key.split("{")[0]
                label_part = key[len(name):]
                if name not in declared:
                    lines.append(f"# TYPE {name} histogram")
                    declared.add(name)
                lines.append(f"{name}_count{label_part} {len(vals)}")
                lines.append(f"{name}_sum{label_part} {sum(vals):.6f}")
        return "\n".join(lines) + "\n"


metrics = Metrics()
