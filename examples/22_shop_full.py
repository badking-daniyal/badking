"""ربات فروشگاه BADKING — نمونه کسبوکاری کامل.

قابلیتها:
  • منوی دکمهای (Inline Keyboard)
  • کاتالوگ محصولات
  • سبد خرید پایدار (به ازای هر کاربر، داخل FSM storage)
  • تعداد محصول، حذف، و جمع کل
  • ثبت سفارش با FSM (نام + شماره)

اجرا:
  py examples/shop_bot.py --mock     # بدون توکن
  py examples/shop_bot.py            # با BADKING_TOKEN
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking import (  # noqa: E402
    Bot,
    Dispatcher,
    F,
    MemoryStorage,
    State,
    StatesGroup,
)
from badking.types.keyboard import InlineKeyboardButton, InlineKeyboardMarkup  # noqa: E402

# ---------- محصولات (قابل ویرایش) ----------
PRODUCTS = {
    "book": {"name": "کتاب پایتون", "price": 250000},
    "course": {"name": "دوره بلهبات", "price": 990000},
    "coffee": {"name": "قهوه specialty", "price": 180000},
}


class OrderStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


# ---------- کیبوردها ----------
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 کاتالوگ", callback_data="menu:catalog")],
        [InlineKeyboardButton(text="🛒 سبد خرید", callback_data="menu:cart")],
        [InlineKeyboardButton(text="ℹ️ درباره ما", callback_data="menu:about")],
    ])


def catalog_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{p['name']} — {p['price']:,} تومان",
            callback_data=f"add:{pid}",
        )]
        for pid, p in PRODUCTS.items()
    ]
    rows.append([InlineKeyboardButton(text="🛒 سبد خرید", callback_data="menu:cart")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_keyboard(cart: dict[str, int]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"❌ حذف {PRODUCTS[pid]['name']}", callback_data=f"remove:{pid}")]
        for pid in cart if pid in PRODUCTS
    ]
    if cart:
        rows.append([InlineKeyboardButton(text="✅ ثبت سفارش", callback_data="order:confirm")])
    rows.append([InlineKeyboardButton(text="🛍 کاتالوگ", callback_data="menu:catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- کمککنندههای سبد ----------
async def get_cart(state) -> dict[str, int]:
    data = await state.get_data()
    return dict(data.get("cart", {}))


async def save_cart(state, cart: dict[str, int]) -> None:
    await state.update_data(cart=cart)


def cart_text(cart: dict[str, int]) -> str:
    if not cart:
        return "🛒 سبد خریدت خالی است.\nبرای دیدن محصولات، کاتالوگ را باز کن."
    lines, total = [], 0
    for pid, qty in cart.items():
        p = PRODUCTS.get(pid)
        if not p:
            continue
        amount = p["price"] * qty
        total += amount
        lines.append(f"• {p['name']} × {qty} — {amount:,} تومان")
    lines.append(f"\n💰 جمع کل: {total:,} تومان")
    return "🛒 سبد خرید:\n" + "\n".join(lines)


async def show_cart(chat_id: int, bot: Bot, state) -> None:
    cart = await get_cart(state)
    await bot.send_message(chat_id, cart_text(cart), reply_markup=cart_keyboard(cart))


# ---------- ربات ----------
def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    @dp.message(F.text == "/start")
    async def start(message, bot):
        await bot.send_message(
            message.chat.id,
            "سلام! به فروشگاه BADKING خوش آمدید 👋\nیکی از گزینهها را انتخاب کن:",
            reply_markup=main_menu(),
        )

    @dp.message(F.text == "/help")
    async def help_cmd(message, bot):
        await bot.send_message(message.chat.id, "دستورها: /start , /cart , /help")

    @dp.message(F.text == "/cart")
    async def cart_cmd(message, bot, state):
        await show_cart(message.chat.id, bot, state)

    # ---------- دکمهها ----------
    @dp.callback_query(F.callback_data == "menu:catalog")
    async def catalog(callback_query, bot):
        await callback_query.answer()
        await bot.send_message(callback_query.message.chat.id, "📚 محصولات:", reply_markup=catalog_keyboard())

    @dp.callback_query(F.callback_data == "menu:about")
    async def about(callback_query, bot):
        await callback_query.answer()
        await bot.send_message(
            callback_query.message.chat.id,
            "فروشگاه نمونه BADKING 🤖\nساختهشده با فریمورک badking.",
            reply_markup=main_menu(),
        )

    @dp.callback_query(F.callback_data == "menu:back")
    async def back(callback_query, bot):
        await callback_query.answer()
        await bot.send_message(callback_query.message.chat.id, "منوی اصلی:", reply_markup=main_menu())

    @dp.callback_query(F.callback_data.startswith("add:"))
    async def add_to_cart(callback_query, bot, state):
        pid = callback_query.data.split(":", 1)[1]
        product = PRODUCTS.get(pid)
        if not product:
            await callback_query.answer("محصول یافت نشد", show_alert=True)
            return
        cart = await get_cart(state)
        cart[pid] = cart.get(pid, 0) + 1
        await save_cart(state, cart)
        await callback_query.answer(f"{product['name']} اضافه شد ✅")
        await bot.send_message(
            callback_query.message.chat.id,
            f"✅ {product['name']} به سبد اضافه شد.\nبرای دیدن سبد /cart بزن.",
        )

    @dp.callback_query(F.callback_data.startswith("remove:"))
    async def remove_from_cart(callback_query, bot, state):
        pid = callback_query.data.split(":", 1)[1]
        cart = await get_cart(state)
        cart.pop(pid, None)
        await save_cart(state, cart)
        await callback_query.answer("حذف شد")
        await show_cart(callback_query.message.chat.id, bot, state)

    @dp.callback_query(F.callback_data == "menu:cart")
    async def cart_callback(callback_query, bot, state):
        await callback_query.answer()
        await show_cart(callback_query.message.chat.id, bot, state)

    @dp.callback_query(F.callback_data == "order:confirm")
    async def order_confirm(callback_query, bot, state):
        cart = await get_cart(state)
        if not cart:
            await callback_query.answer("سبدت خالی است", show_alert=True)
            return
        await callback_query.answer()
        await state.set_state(OrderStates.waiting_name)
        await bot.send_message(callback_query.message.chat.id, "لطفاً نام خود را بفرست:")

    # ---------- FSM: ثبت سفارش ----------
    @dp.message()
    async def fsm_flow(message, bot, state):
        current = await state.get_state()
        if current == OrderStates.waiting_name.name:
            await state.update_data(name=message.text)
            await state.set_state(OrderStates.waiting_phone)
            await bot.send_message(message.chat.id, "شماره تلفنت رو بفرست:")
        elif current == OrderStates.waiting_phone.name:
            data = await state.get_data()
            cart = data.get("cart", {})
            total = sum(PRODUCTS[p]["price"] * q for p, q in cart.items() if p in PRODUCTS)
            await bot.send_message(
                message.chat.id,
                f"✅ سفارش ثبت شد!\nنام: {data.get('name')}\nتلفن: {message.text}\n"
                f"مبلغ: {total:,} تومان\nبهزودی باهات تماس میگیریم.",
                reply_markup=main_menu(),
            )
            await state.clear()
        else:
            await bot.send_message(
                message.chat.id,
                "از منو استفاده کن یا /start بزن.",
                reply_markup=main_menu(),
            )

    return dp


# ---------- اجرا ----------
async def run_mock() -> None:
    import httpx
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
    from mock_server import BaleMock

    mock = BaleMock()
    for text in ("/start",):
        mock.add_message(text)
    client = httpx.AsyncClient(transport=mock.transport())
    bot = Bot("1:MOCK", client=client)
    dp = build_dispatcher()
    for u in await bot.get_updates():
        await dp.process(u, bot)
    print("--- پیام ارسالشده توسط فروشگاه (mock) ---")
    for sent in mock.sent:
        print("→", sent["text"][:80])
        rows = sent.get("reply_markup", {}).get("inline_keyboard", [])
        print("  دکمهها:", [b.get("text") for row in rows for b in row])
    await bot.close()


async def run_real() -> None:
    token = os.environ.get("BADKING_TOKEN")
    if not token or token == "TOKEN":
        print("توکن پیدا نشد. `badking setup` را اجرا کن.")
        return
    bot = Bot(token)
    dp = build_dispatcher()
    print("فروشگاه BADKING در حال اجرا... (Ctrl+C برای توقف)")
    await bot.polling(dp)


if __name__ == "__main__":
    if "--mock" in sys.argv:
        asyncio.run(run_mock())
    else:
        asyncio.run(run_real())
