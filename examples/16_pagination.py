"""صفحه‌بندی: لیست بلند در چند صفحه.

هدف: ۱۰۰ محصول را در صفحه‌های ۵ تایی نشان بدهی.

    python 16_pagination.py
"""

import asyncio
import os

from badking import Bot, CallbackData, F, InlineKeyboardBuilder, KeyboardPaginator

PageCB = CallbackData("page", "number")

ITEMS = [f"محصول شماره {i}" for i in range(1, 101)]
PER_PAGE = 5


def page_count() -> int:
    return (len(ITEMS) + PER_PAGE - 1) // PER_PAGE


def page_items(page: int) -> list[str]:
    start = (page - 1) * PER_PAGE
    return ITEMS[start : start + PER_PAGE]


def build_keyboard(page: int):
    """کیبورد صفحه: ردیف آیتم‌ها + ردیف ناوبری."""
    kb = InlineKeyboardBuilder()

    # آیتم‌های این صفحه
    for item in page_items(page):
        kb.button(item, callback_data=PageCB(number=page).pack())

    # ناوبری
    total = page_count()
    if page > 1:
        kb.button("◀ قبلی", callback_data=PageCB(number=page - 1).pack())
    kb.button(f"{page} / {total}", callback_data="noop")
    if page < total:
        kb.button("بعدی ▶", callback_data=PageCB(number=page + 1).pack())

    # ردیف آیتم‌ها یک‌تایی، ردیف ناوبری سه‌تایی
    kb.adjust(1, 1, 1, 1, 1, 3)
    return kb.as_markup()


def render(page: int) -> str:
    items = page_items(page)
    lines = [f"صفحه {page} از {page_count()}", ""]
    lines += [f"• {item}" for item in items]
    return "\n".join(lines)


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    @bot.on_message(F.text == "/list")
    async def show_list(message):
        await message.reply(render(1), reply_markup=build_keyboard(1))

    @bot.on_callback(F.data.startswith("page:"))
    async def change_page(callback):
        data = PageCB.unpack(callback.data)
        page = max(1, min(data.number, page_count()))

        await callback.message.edit_text(
            render(page),
            reply_markup=build_keyboard(page),
        )
        await callback.answer()

    @bot.on_callback(F.data == "noop")
    async def noop(callback):
        await callback.answer()

    print("ربات روشن شد. /list را بزن.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
