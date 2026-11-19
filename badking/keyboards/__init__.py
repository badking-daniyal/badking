"""KeyboardPaginator — منوهای چندصفحه‌ای با دکمه‌های صفحه بعد/قبل.

مثال:
    paginator = KeyboardPaginator(items, per_page=5, prefix="item")
    markup = paginator.markup(page=0)          # InlineKeyboardMarkup
    items_on_page = paginator.page_items(0)

    @dp.callback_query(F.data.startswith("item:"))
    async def on_item(cq, bot):
        page = int(cq.data.split(":")[1])
        ...
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from ..types.keyboard import InlineKeyboardButton, InlineKeyboardMarkup
from .builder import InlineKeyboardBuilder, ReplyKeyboardBuilder


class KeyboardPaginator:
    """صفحه‌بندی دکمه‌های inline با دکمه‌های ناوبری خودکار."""

    def __init__(
        self,
        items: Sequence[Any],
        *,
        per_page: int = 5,
        prefix: str = "page",
        label: Callable[[Any], str] | None = None,
        callback: Callable[[Any], str] | None = None,
        columns: int = 1,
        nav_labels: tuple[str, str, str] = ("« قبلی", "بستن", "بعدی »"),
    ):
        if per_page < 1:
            raise ValueError("per_page باید حداقل ۱ باشد")
        self.items = list(items)
        self.per_page = per_page
        self.prefix = prefix
        self.label = label or (lambda x: str(x))
        self.callback = callback
        self.columns = max(1, columns)
        self.nav_labels = nav_labels

    @property
    def page_count(self) -> int:
        if not self.items:
            return 1
        return (len(self.items) + self.per_page - 1) // self.per_page

    def page_items(self, page: int) -> list[Any]:
        """آیتم‌های یک صفحه."""
        page = max(0, min(page, self.page_count - 1))
        start = page * self.per_page
        return self.items[start:start + self.per_page]

    def _cb(self, item: Any, index: int) -> str:
        if self.callback:
            return self.callback(item)
        return f"{self.prefix}:item:{index}"

    def markup(self, page: int = 0) -> InlineKeyboardMarkup:
        """کیبورد صفحه مشخص."""
        page = max(0, min(page, self.page_count - 1))
        start = page * self.per_page
        rows: list[list[InlineKeyboardButton]] = []

        row: list[InlineKeyboardButton] = []
        for offset, item in enumerate(self.page_items(page)):
            row.append(InlineKeyboardButton(
                text=self.label(item),
                callback_data=self._cb(item, start + offset),
            ))
            if len(row) >= self.columns:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

        # ردیف ناوبری
        nav: list[InlineKeyboardButton] = []
        prev_label, close_label, next_label = self.nav_labels
        if page > 0:
            nav.append(InlineKeyboardButton(
                text=prev_label, callback_data=f"{self.prefix}:page:{page - 1}"))
        if self.page_count > 1:
            nav.append(InlineKeyboardButton(
                text=f"{page + 1}/{self.page_count}",
                callback_data=f"{self.prefix}:noop"))
        if page < self.page_count - 1:
            nav.append(InlineKeyboardButton(
                text=next_label, callback_data=f"{self.prefix}:page:{page + 1}"))
        if nav:
            rows.append(nav)

        return InlineKeyboardMarkup(inline_keyboard=rows)

    def parse(self, callback_data: str) -> tuple[str, int] | None:
        """تجزیه callback_data: ('page', n) یا ('item', n) یا None."""
        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != self.prefix:
            return None
        kind, value = parts[1], parts[2]
        if kind == "noop":
            return None
        try:
            return kind, int(value)
        except ValueError:
            return None
