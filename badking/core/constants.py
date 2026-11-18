"""ثابتها و محدودیتها.

قاعده مهم: اعدادی که در مستندات رسمی بله نیامدهاند، پیشفرض قابلتنظیماند
و با پاسخ واقعی سرور (retry_after) calibrate میشوند.
"""

from __future__ import annotations

from dataclasses import dataclass, field

API_BASE = "https://tapi.bale.ai"
DEFAULT_TIMEOUT = 30.0
WEBHOOK_PORTS = (443, 88)  # تأیید شده: docs.bale.ai/#setwebhook
UPDATE_RETENTION_HOURS = 24  # تأیید شده
MAX_CACHED_UPDATES = 2000  # تأیید شده

# تأییدنشده در مستندات رسمی — پیشفرض قابلتنظیم، نه حقیقت
UNVERIFIED_DEFAULTS = {
    "max_text_length": 4096,
    "max_caption_length": 1024,
    "max_callback_data_bytes": 64,
    "delete_message_after_hours": 48,
    "pre_checkout_timeout_seconds": 10,
    "rate_per_second": 2,
    "rate_burst_per_second": 20,
    "rate_per_minute": 120,
}


@dataclass
class Limits:
    """محدودیتهای قابلتنظیم. مقادیر تأییدنشده با retry_after سرور بهروز میشوند."""

    max_text_length: int = UNVERIFIED_DEFAULTS["max_text_length"]
    max_caption_length: int = UNVERIFIED_DEFAULTS["max_caption_length"]
    max_callback_data_bytes: int = UNVERIFIED_DEFAULTS["max_callback_data_bytes"]
    delete_message_after_hours: int = UNVERIFIED_DEFAULTS["delete_message_after_hours"]
    pre_checkout_timeout_seconds: int = UNVERIFIED_DEFAULTS["pre_checkout_timeout_seconds"]
    rate_per_second: int = UNVERIFIED_DEFAULTS["rate_per_second"]
    rate_burst_per_second: int = UNVERIFIED_DEFAULTS["rate_burst_per_second"]
    rate_per_minute: int = UNVERIFIED_DEFAULTS["rate_per_minute"]
    observed: dict[str, int] = field(default_factory=dict)

    def calibrate_from_response(self, retry_after: float | None, error_code: int | None) -> None:
        """یادگیری از پاسخ واقعی سرور."""
        import math
        if error_code == 429 and retry_after is not None:
            secs = max(0.001, float(retry_after))
            self.observed["retry_after_seconds"] = secs
            # نرخ جدید: حداکثر 1 پیام در هر `secs` ثانیه
            new_rate = max(1, int(math.floor(1.0 / secs)))
            self.rate_per_second = min(self.rate_per_second, new_rate)
            self.rate_per_minute = min(self.rate_per_minute, max(1, int(60.0 / secs)))
