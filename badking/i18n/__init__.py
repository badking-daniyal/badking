"""بومی‌سازی — پیام‌های ربات به زبان کاربر.

    from badking.i18n import Translator, fa, en

    t = Translator(fa, en, default="fa")

    t("welcome", name="دانیال")     # «سلام دانیال»
    t("welcome", name="Danial", lang="en")  # "Hello Danial"

چرا لازم است: رباتی که فقط فارسی حرف می‌زند، نیمی از مخاطبش را از دست
می‌دهد. رباتی که فقط انگلیسی حرف می‌زند، در ایران استفاده نمی‌شود.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("badking.i18n")


class TranslationError(Exception):
    """کلید ترجمه پیدا نشد، یا پارامتر لازم نبود."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message}\n  → {self.hint}" if self.hint else self.message


@dataclass
class Catalog:
    """یک زبان: کلید → متن.

        catalog = Catalog("fa", {
            "welcome": "سلام {name}",
            "bye": "خداحافظ",
        })
    """

    lang: str
    strings: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        return self.strings.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self.strings

    def __len__(self) -> int:
        return len(self.strings)


class Translator:
    """ترجمه با fallback.

        t = Translator(fa_catalog, en_catalog, default="fa")
        t("welcome", name="دانیال")
        t("welcome", name="Danial", lang="en")

    اگر کلیدی در زبان درخواستی نبود، از زبان پیش‌فرض می‌آید. اگر آنجا هم
    نبود، خود کلید برگردانده می‌شود — ربات نمی‌شکند، فقط متن خام نشان
    می‌دهد.
    """

    def __init__(self, *catalogs: Catalog, default: str = "fa") -> None:
        self._catalogs: dict[str, Catalog] = {c.lang: c for c in catalogs}
        self.default = default

        if default not in self._catalogs:
            raise TranslationError(
                f"زبان پیش‌فرض {default!r} در کاتالوگ‌ها نیست",
                hint=f"یکی از این‌ها را بده: {list(self._catalogs)}",
            )

    @property
    def languages(self) -> list[str]:
        """زبان‌های موجود."""
        return list(self._catalogs)

    def add(self, catalog: Catalog) -> None:
        """زبان جدید اضافه می‌کند."""
        self._catalogs[catalog.lang] = catalog

    def has(self, key: str, lang: str | None = None) -> bool:
        """آیا این کلید ترجمه دارد؟"""
        catalog = self._catalogs.get(lang or self.default)
        return bool(catalog and key in catalog)

    def missing(self, lang: str) -> list[str]:
        """کلیدهایی که در این زبان نیستند ولی در پیش‌فرض هستند."""
        target = self._catalogs.get(lang)
        base = self._catalogs.get(self.default)
        if not target or not base:
            return []
        return [key for key in base.strings if key not in target]

    def __call__(
        self,
        key: str,
        *,
        lang: str | None = None,
        **params: Any,
    ) -> str:
        """متن ترجمه‌شده با پارامترها."""
        language = lang or self.default

        catalog = self._catalogs.get(language)
        text = catalog.get(key) if catalog else None

        if text is None:
            # fallback به زبان پیش‌فرض
            base = self._catalogs.get(self.default)
            text = base.get(key) if base else None

        if text is None:
            log.warning("کلید ترجمه پیدا نشد: %s (زبان %s)", key, language)
            return key

        if not params:
            # حتی بدون پارامتر هم format می‌زنیم: اگر متن جای‌نگهدار داشته
            # باشد و پارامتری نرسیده باشد، باید خطا بدهد نه اینکه {name}
            # خام به کاربر نشان داده شود.
            try:
                return text.format()
            except (IndexError, ValueError) as exc:
                raise TranslationError(
                    f"قالب کلید {key!r} خراب است: {exc}",
                    hint="آکولادها را بررسی کن. برای آکولاد خام از {{ }} استفاده کن.",
                ) from exc
            except KeyError as exc:
                raise TranslationError(
                    f"پارامتر {exc} در کلید {key!r} لازم است",
                    hint="مقدارش را به عنوان آرگومان نام‌دار بده.",
                ) from exc

        try:
            return text.format(**params)
        except KeyError as exc:
            raise TranslationError(
                f"پارامتر {exc} در کلید {key!r} لازم است",
                hint=f"پارامترهای موجود: {list(params)}",
            ) from exc
        except (IndexError, ValueError) as exc:
            raise TranslationError(
                f"قالب کلید {key!r} خراب است: {exc}",
                hint="آکولادها را بررسی کن. برای آکولاد خام از {{ }} استفاده کن.",
            ) from exc


# ---------- کاتالوگ‌های آماده ----------

fa = Catalog(
    "fa",
    {
        # عمومی
        "welcome": "سلام {name}!",
        "bye": "خداحافظ",
        "cancel": "لغو شد.",
        "error": "خطایی رخ داد. دوباره تلاش کن.",
        "not_found": "پیدا نشد.",
        "done": "انجام شد.",
        "loading": "در حال پردازش...",
        "yes": "بله",
        "no": "خیر",
        "back": "بازگشت",
        "next": "بعدی",
        "previous": "قبلی",
        # دسترسی
        "access_denied": "این بخش برای ادمین است.",
        "not_admin": "من ادمین نیستم. اول ادمینم کن.",
        # فرم
        "ask_name": "اسمت چیه؟",
        "ask_age": "چند سالته؟",
        "ask_phone": "شماره تماست؟",
        "ask_city": "کدام شهر؟",
        "invalid_number": "یک عدد معتبر بفرست.",
        "invalid_phone": "شماره را درست بفرست. مثال: ۰۹۱۲۳۴۵۶۷۸۹",
        "form_done": "ثبت شد:\n{summary}",
        # فروشگاه
        "shop_title": "محصولی انتخاب کن:",
        "cart_empty": "سبد خرید خالی است.",
        "cart_total": "جمع: {total} تومان",
        "added_to_cart": "{name} اضافه شد",
        "out_of_stock": "موجودی کافی نیست",
        "order_placed": "سفارش ثبت شد.",
        # خطا
        "rate_limited": "کمی آرام‌تر. {seconds} ثانیه صبر کن.",
        "flood_wait": "سرور شلوغ است. {seconds} ثانیه صبر کن.",
        "network_error": "اتصال قطع شد. دوباره تلاش می‌کنم.",
        # زمان
        "today": "امروز",
        "yesterday": "دیروز",
    },
)

en = Catalog(
    "en",
    {
        "welcome": "Hello {name}!",
        "bye": "Goodbye",
        "cancel": "Cancelled.",
        "error": "Something went wrong. Try again.",
        "not_found": "Not found.",
        "done": "Done.",
        "loading": "Processing...",
        "yes": "Yes",
        "no": "No",
        "back": "Back",
        "next": "Next",
        "previous": "Previous",
        "access_denied": "This section is for admins.",
        "not_admin": "I am not an admin. Promote me first.",
        "ask_name": "What is your name?",
        "ask_age": "How old are you?",
        "ask_phone": "What is your phone number?",
        "ask_city": "Which city?",
        "invalid_number": "Send a valid number.",
        "invalid_phone": "Send a valid phone number. Example: 09123456789",
        "form_done": "Saved:\n{summary}",
        "shop_title": "Pick a product:",
        "cart_empty": "Your cart is empty.",
        "cart_total": "Total: {total}",
        "added_to_cart": "{name} added",
        "out_of_stock": "Not enough stock",
        "order_placed": "Order placed.",
        "rate_limited": "Slow down. Wait {seconds} seconds.",
        "flood_wait": "Server is busy. Wait {seconds} seconds.",
        "network_error": "Connection lost. Retrying.",
        "today": "Today",
        "yesterday": "Yesterday",
    },
)


def default_translator() -> Translator:
    """مترجم پیش‌فرض با فارسی و انگلیسی."""
    return Translator(fa, en, default="fa")


__all__ = [
    "Catalog",
    "TranslationError",
    "Translator",
    "default_translator",
    "en",
    "fa",
]
