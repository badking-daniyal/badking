"""سازنده کیبورد شیشه‌ای — ساخت دکمه‌ها بدون دست‌کاری dict.

    from badking.keyboards import InlineKeyboardBuilder

    kb = (
        InlineKeyboardBuilder()
        .button("وب‌سایت", url="https://badking.ir")
        .button("کلیک", callback_data="btn:1")
        .button("کپی کد", copy_text="CODE123")
        .adjust(2)
        .as_markup()
    )
"""

from __future__ import annotations

from typing import Any

from ..types.keyboard import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


class InlineKeyboardBuilder:
    """سازنده روان برای کیبورد شیشه‌ای.

    هر `button()` یک دکمه اضافه می‌کند و خودش را برمی‌گرداند، پس زنجیره
    می‌شود. `adjust()` تعیین می‌کند هر ردیف چند دکمه داشته باشد.
    """

    def __init__(self) -> None:
        self._buttons: list[InlineKeyboardButton] = []
        self._sizes: list[int] = []

    @property
    def buttons(self) -> list[InlineKeyboardButton]:
        return self._buttons

    def button(
        self,
        text: str,
        url: str | None = None,
        callback_data: str | None = None,
        copy_text: str | None = None,
        web_app: str | None = None,
        style: str | None = None,
    ) -> "InlineKeyboardBuilder":
        """یک دکمه اضافه می‌کند.

        فقط یکی از `url` / `callback_data` / `copy_text` / `web_app` معنا دارد؛
        اگر چندتا بدهی، بله اولی را می‌گیرد.
        """
        self._buttons.append(
            InlineKeyboardButton(
                text=text,
                url=url,
                callback_data=callback_data,
                copy_text=CopyTextButton(text=copy_text) if copy_text else None,
                web_app={"url": web_app} if web_app else None,
                style=style,
            )
        )
        return self

    def add(self, *buttons: InlineKeyboardButton) -> "InlineKeyboardBuilder":
        """دکمه‌های آماده را اضافه می‌کند."""
        self._buttons.extend(buttons)
        return self

    def row(self, *buttons: InlineKeyboardButton) -> "InlineKeyboardBuilder":
        """یک ردیف کامل. معادل `add` است؛ ردیف‌بندی با `adjust` تعیین می‌شود."""
        self._buttons.extend(buttons)
        return self

    def attach(self, other: "InlineKeyboardBuilder") -> "InlineKeyboardBuilder":
        """دکمه‌های سازنده دیگر را قرض می‌گیرد."""
        self._buttons.extend(other._buttons)
        return self

    def adjust(self, *sizes: int) -> "InlineKeyboardBuilder":
        """الگوی ردیف‌بندی. `adjust(2)` یعنی دو دکمه در هر ردیف؛
        `adjust(1, 2)` یعنی یک، دو، یک، دو..."""
        self._sizes = list(sizes) if sizes else [1]
        return self

    def export(self, *sizes: int) -> list[list[InlineKeyboardButton]]:
        """دکمه‌ها را به ردیف‌ها می‌شکند."""
        layout = list(sizes) if sizes else (self._sizes if self._sizes else [1])
        result: list[list[InlineKeyboardButton]] = []
        pending = list(self._buttons)
        idx = 0

        while pending:
            size = layout[idx % len(layout)]
            result.append(pending[:size])
            pending = pending[size:]
            idx += 1

        return result

    def as_markup(self, *sizes: int) -> InlineKeyboardMarkup:
        """خروجی آماده برای `reply_markup`."""
        return InlineKeyboardMarkup(inline_keyboard=self.export(*sizes))

    def as_dict(self, *sizes: int) -> dict[str, Any]:
        """همان چیز، به‌صورت dict خام."""
        return {
            "inline_keyboard": [
                [btn.model_dump(exclude_none=True) for btn in row]
                for row in self.export(*sizes)
            ]
        }


class ReplyKeyboardBuilder:
    """سازنده کیبورد پایین صفحه (Reply Keyboard)."""

    def __init__(self) -> None:
        self._buttons: list[KeyboardButton] = []
        self._sizes: list[int] = []

    def button(
        self,
        text: str,
        request_contact: bool = False,
        request_location: bool = False,
        web_app: str | None = None,
    ) -> "ReplyKeyboardBuilder":
        self._buttons.append(
            KeyboardButton(
                text=text,
                request_contact=request_contact or None,
                request_location=request_location or None,
                web_app={"url": web_app} if web_app else None,
            )
        )
        return self

    def adjust(self, *sizes: int) -> "ReplyKeyboardBuilder":
        self._sizes = list(sizes) if sizes else [1]
        return self

    def as_markup(
        self,
        resize_keyboard: bool = True,
        one_time_keyboard: bool = False,
        placeholder: str | None = None,
    ) -> ReplyKeyboardMarkup:
        layout = self._sizes if self._sizes else [1]
        rows: list[list[KeyboardButton]] = []
        pending = list(self._buttons)
        idx = 0
        while pending:
            size = layout[idx % len(layout)]
            rows.append(pending[:size])
            pending = pending[size:]
            idx += 1

        return ReplyKeyboardMarkup(
            keyboard=rows,
            resize_keyboard=resize_keyboard,
            one_time_keyboard=one_time_keyboard or None,
            input_field_placeholder=placeholder,
        )


__all__ = ["InlineKeyboardBuilder", "ReplyKeyboardBuilder"]
