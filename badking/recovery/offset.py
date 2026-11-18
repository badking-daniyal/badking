"""Update Recovery — ذخیره offset و جبران آپدیتهای ازدسترفته.

بله فقط ۲۴ ساعت / ۲۰۰۰ پیام را نگه میدارد؛ بنابراین offset باید پایدار ذخیره شود.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class OffsetStore:
    """ذخیره ساده offset روی فایل (قابل تعویض با Redis/DB)."""

    def __init__(self, path: str = "badking_offset.json"):
        self.path = Path(path)

    def load(self) -> int:
        if not self.path.exists():
            return 0
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return int(data.get("offset", 0))
        except Exception:
            import logging
            logging.getLogger("badking").warning("فایل offset خراب است: %s", self.path)
            return 0

    def save(self, offset: int) -> None:
        # نوشتن اتمیک: ابتدا فایل موقت، سپس جایگزینی (جلوگیری از فایل ناقص هنگام crash)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({"offset": int(offset)}), encoding="utf-8")
        os.replace(str(tmp), str(self.path))

    def reset(self) -> None:
        if self.path.exists():
            self.path.unlink()
