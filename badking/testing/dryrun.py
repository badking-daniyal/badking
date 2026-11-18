"""Dry-run Mode — ربات را بدون فرستادن پیام واقعی تست کن.

برای کسی که کد بلد نیست حیاتی است: میبینی ربات چی میفرستاد، بدون اینکه بفرستد.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SentMessage:
    chat_id: Any
    text: str
    kwargs: dict[str, Any] = field(default_factory=dict)


class DryBot:
    """جایگزین Bot که پیامها را ضبط میکند بجای ارسال."""

    def __init__(self, real_bot: Any = None):
        self.real_bot = real_bot
        self.sent: list[SentMessage] = []

    async def send_message(self, chat_id: Any, text: str, **kwargs: Any) -> Any:
        self.sent.append(SentMessage(chat_id, text, kwargs))
        return None

    async def answer_callback_query(self, *args: Any, **kwargs: Any) -> bool:
        return True

    async def request(self, method: str, params: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return None

    def summary(self) -> str:
        return "\n".join(f"→ [{m.chat_id}] {m.text}" for m in self.sent) or "(پیامی ارسال نشد)"
