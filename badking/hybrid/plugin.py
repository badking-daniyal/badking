"""لایه Hybrid — چارچوب ایزوله self-bot (غیرفعال پیشفرض).

هیچ اتصال داخلی به API بله در این فایل وجود ندارد. این فقط قرارداد و ایزولاسیون است.
پیادهسازی real internal RPC بهصورت پلاگین جداگانه و اختیاری است.
"""

from __future__ import annotations

from typing import Any


class HybridDisabledError(Exception):
    """سعی در استفاده از self-bot بدون تأیید ریسک."""


HYBRID_WARNING = (
    "⚠️  HYBRID / SELF-BOT MODE\n"
    "  • از Internal API غیررسمی بله استفاده میکند (قابل شکستن).\n"
    "  • نیاز به لاگین شماره تلفن دارد، نه توکن رسمی.\n"
    "  • خطر بسته شدن اکانت شخصی وجود دارد.\n"
    "  • اسرار را فقط در keyring سیستم ذخیره کن.\n"
)


def hybrid_warning() -> str:
    return HYBRID_WARNING


class HybridPlugin:
    """پلاگین ایزوله self-bot.

    بدون ack_risk=True هرگز فعال نمیشود.
    """

    def __init__(self, *, enabled: bool = False, ack_risk: bool = False,
                 storage: Any = None, dispatcher: Any = None):
        self.enabled = enabled and ack_risk
        self.ack_risk = ack_risk
        self.storage = storage
        self.dispatcher = dispatcher
        self._lane_name = "selfbot"

    def activate(self) -> None:
        if not self.enabled:
            raise HybridDisabledError(
                "Self-bot فعال نیست. برای فعالسازی آگاهانه: "
                "HybridPlugin(enabled=True, ack_risk=True)"
            )

    @property
    def lane(self) -> str:
        return self._lane_name

    def register_rpc(self, name: str, handler: Any) -> None:
        """ثبت متد RPC داخلی (فقط زمانی که لایه فعال است)."""
        self.activate()
        setattr(self, name, handler)

    async def iter_messages(self, chat_id: Any, limit: int = 50):
        """جایگاه خواندن تاریخچه (پیادهسازی internal RPC جداگانه است)."""
        self.activate()
        raise NotImplementedError(
            "iter_messages نیاز به پلاگین internal RPC دارد (post-release، اختیاری)."
        )
