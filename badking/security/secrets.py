"""مدیریت ایمن اسرار — توکنها در محیط/keyring، نه در کد.

قاعده امنیتی BADKING: هیچ توکنی در سورس کد ننویس.
"""

from __future__ import annotations

import os
from typing import Any


class Secrets:
    """خواندن اسرار از محیط با پشتیبانی keyring اختیاری."""

    def __init__(self, prefix: str = "BADKING_"):
        self.prefix = prefix

    def get(self, name: str, default: str | None = None) -> str | None:
        key = name if name.startswith(self.prefix) else f"{self.prefix}{name}"
        value = os.environ.get(key)
        if value is not None:
            return value
        # تلاش اختیاری برای keyring سیستم
        try:
            import keyring  # type: ignore
            return keyring.get_password("badking", key) or default
        except Exception:
            return default

    def set_keyring(self, name: str, value: str) -> bool:
        """ذخیره در keyring سیستم (در صورت نصب بودن)."""
        try:
            import keyring  # type: ignore
            key = name if name.startswith(self.prefix) else f"{self.prefix}{name}"
            keyring.set_password("badking", key, value)
            return True
        except Exception:
            return False

    @staticmethod
    def mask(value: str | None) -> str:
        """پنهان کردن توکن در لاگها."""
        if not value:
            return "<none>"
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}{'*' * 8}{value[-4:]}"
