"""اشتراک تستها: تنظیم event loop تازه برای هر تست (سازگار با Python 3.9).

روی Python 3.9 بعد از asyncio.run() حلقه بسته میشود و get_event_loop()
دیگر کار نمیکند. این fixture تضمین میکند ترتیب اجرای تستها مهم نباشد.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _fresh_event_loop():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    yield
    # حلقه را برای تست بعدی تمیز نگه میداریم (بسته نمیشود)
