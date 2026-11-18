"""Anti-spam — محدودکننده کاربر، Captcha ساده، و لیست مسدود."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any


class AntiSpam:
    """جلوگیری از اسپم: حداکثر N پیام در بازه T ثانیه."""

    def __init__(self, max_messages: int = 5, window_seconds: float = 10.0,
                 ban_seconds: float = 60.0):
        self.max_messages = max_messages
        self.window = window_seconds
        self.ban_seconds = ban_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._banned: dict[str, float] = {}
        self._blocklist: set[str] = set()

    def is_allowed(self, user_id: Any) -> bool:
        key = str(user_id)
        now = time.time()
        if key in self._blocklist:
            return False
        until = self._banned.get(key, 0)
        if until > now:
            return False
        if until and until <= now:
            self._banned.pop(key, None)

        hits = self._hits[key]
        while hits and hits[0] < now - self.window:
            hits.popleft()
        if len(hits) >= self.max_messages:
            self._banned[key] = now + self.ban_seconds
            # hits.clear() نباید شود: پاک کردن سابقه پنجره زمانی به اسپمر
            # اجازه میدهد بعد از بن دوباره سهمیه کامل بگیرد. بگذار پنجره
            # بهطور طبیعی تخلیه شود.
            return False
        hits.append(now)
        return True

    def block(self, user_id: Any) -> None:
        self._blocklist.add(str(user_id))

    def unblock(self, user_id: Any) -> None:
        key = str(user_id)
        self._blocklist.discard(key)
        self._banned.pop(key, None)


class Captcha:
    """Captcha ساده: کاربر باید پاسخ صحیح را بدهد."""

    def __init__(self):
        self._pending: dict[str, str] = {}

    def challenge(self, user_id: Any) -> str:
        import random
        a, b = random.randint(1, 9), random.randint(1, 9)
        question = f"{a} + {b} = ؟"
        self._pending[str(user_id)] = str(a + b)
        return question

    def verify(self, user_id: Any, answer: str) -> bool:
        key = str(user_id)
        expected = self._pending.get(key)
        if expected is None:
            return False
        ok = answer.strip() == expected
        if ok:
            self._pending.pop(key, None)
        return ok
