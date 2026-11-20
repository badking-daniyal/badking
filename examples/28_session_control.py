"""کنترل سشن — معادل main-3.py، ولی با BADKING.

هدف: پنل مدیریت چند اکانت شخصی بله (self-bot) از طریق یک ربات رسمی.

    set BADKING_TOKEN=123456:ABC
    set BADKING_SESSION_KEY=رمز-قوی
    python examples/28_session_control.py

قابلیتها (همان کاری که main-3.py میکرد، منظمتر):
    • ساخت سشن: شماره → کد SMS → (رمز دومرحلهای)
    • لیست و جستجوی اکانت
    • بررسی سلامت و حذف سشنهای خراب/تکراری
    • جوین/لیو دستهجمعی با لینک و Delay
    • بکاپ/ریستور zip (جایگزین backup.zip)

تفاوت با main-3.py:
    • به جای صدها فایل .bale پراکنده، یک فایل رمزنگاریشده
    • به جای try/except تکراری و client=None، یک SessionManager
    • بکاپ با هش تأیید میشود (دستکاری شده رد میشود)
    • نام فایلها از شماره کاربر میآید، Path Traversal ندارد

هشدار جدی: self-bot از API داخلی بله استفاده میکند و میتواند اکانت را
مسدود کند. BADKING این لایه را پیشفرض خاموش نگه میدارد و تنها با
فعالسازی صریح HybridPlugin قابل استفاده است.
"""

import asyncio
import os
from datetime import datetime

from badking import Bot, Dispatcher, F, ReplyKeyboardBuilder, to_english_digits
from badking.hybrid import SelfBot, SessionManager

TOKEN = os.environ.get("BADKING_TOKEN", "123456:ABC")
ADMINS = {int(x) for x in os.environ.get("BADKING_ADMINS", "123456789").split(",")}
SESSION_FILE = os.environ.get("BADKING_SESSIONS", "sessions.bks")
SESSION_KEY = os.environ.get("BADKING_SESSION_KEY", "") or None

mgr = SessionManager(SESSION_FILE, password=SESSION_KEY)

# وضعیت مکالمه هر ادمین (FSM ساده)
state: dict[int, dict] = {}
DELAY = {"seconds": 2.0}


def main_markup():
    kb = ReplyKeyboardBuilder()
    for text in (
        "📊 اطلاعات کامل", "🔍 بررسی سشنها",
        "📥 جوین دستهجمعی", "📤 لیو دستهجمعی",
        "✨ ساخت سشن", "🎩 برترینها",
        "📦 بکاپ", "📥 ریستور",
        "⏱ تنظیم Delay", "📚 راهنما",
    ):
        kb.button(text)
    kb.adjust(2)
    return kb.as_markup()


def is_admin(user_id: int) -> bool:
    return bool(ADMINS) and user_id in ADMINS


async def edit(status, text: str) -> None:
    """ویرایش پیام وضعیت، با محافظت در برابر خطا."""
    try:
        await status.edit_text(text)
    except Exception:  # noqa: BLE001
        pass


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    @dp.message(F.text == "/start")
    async def start(message, bot):
        if not is_admin(message.from_user.id):
            return
        await bot.send_message(
            message.chat.id,
            f"✨ پنل کنترل سشن BADKING\n"
            f"{mgr.count()} اکانت ذخیره شده\n"
            f"Delay: {DELAY['seconds']:.0f} ثانیه",
            reply_markup=main_markup(),
        )

    @dp.message(F.text == "/cancel")
    async def cancel(message, bot):
        state.pop(message.from_user.id, None)
        await bot.send_message(message.chat.id, "❌ عملیات کنسل شد")

    @dp.message(F.text == "📊 اطلاعات کامل")
    async def full_info(message, bot):
        if not is_admin(message.from_user.id):
            return
        status = await bot.send_message(message.chat.id, "🔄 در حال جمعآوری اطلاعات...")
        accounts = mgr.list_accounts()
        if not accounts:
            await edit(status, "هیچ اکنتی ذخیره نشده است.")
            return

        lines = [f"📊 {len(accounts)} اکانت:", ""]
        for acc in accounts[:20]:
            mark = "✓" if acc.valid else "✗"
            lines.append(f"  {mark} {acc.phone or acc.key} | id={acc.user_id or '?'} | {acc.name}")
        if len(accounts) > 20:
            lines.append(f"  ... و {len(accounts) - 20} اکانت دیگر")
        await edit(status, "\n".join(lines))

    @dp.message(F.text == "🔍 بررسی سشنها")
    async def check_sessions(message, bot):
        if not is_admin(message.from_user.id):
            return
        status = await bot.send_message(message.chat.id, "🔄 بررسی اکانتها شروع شد...")
        report = await mgr.check_all(remove_broken=True)
        await edit(status, report.summary)

    @dp.message(F.text == "✨ ساخت سشن")
    async def ask_phone(message, bot):
        if not is_admin(message.from_user.id):
            return
        state[message.from_user.id] = {"step": "phone"}
        await bot.send_message(message.chat.id, "شماره تلفن را بفرست (مثال: 09123456789)")

    @dp.message(F.text == "📥 جوین دستهجمعی")
    async def ask_join(message, bot):
        if not is_admin(message.from_user.id):
            return
        state[message.from_user.id] = {"step": "join"}
        await bot.send_message(
            message.chat.id,
            "فرمت:\nجوین\n[تعداد]\n[لینک گروه]\n\nمثال:\nجوین\n5\nhttps://ble.ir/join/ABCD",
        )

    @dp.message(F.text == "📤 لیو دستهجمعی")
    async def ask_leave(message, bot):
        if not is_admin(message.from_user.id):
            return
        state[message.from_user.id] = {"step": "leave"}
        await bot.send_message(message.chat.id, "فرمت:\nلیو\n[تعداد]\n[لینک گروه]")

    @dp.message(F.text == "⏱ تنظیم Delay")
    async def ask_delay(message, bot):
        if not is_admin(message.from_user.id):
            return
        state[message.from_user.id] = {"step": "delay"}
        await bot.send_message(message.chat.id, "فاصله به ثانیه (مثلاً 3):")

    @dp.message(F.text == "📦 بکاپ")
    async def backup(message, bot):
        if not is_admin(message.from_user.id):
            return
        path = mgr.export_zip("badking_backup.zip")
        await bot.send_document(
            message.chat.id,
            str(path),
            caption=f"📦 بکاپ {mgr.count()} اکانت\n🗓 {datetime.now():%Y/%m/%d - %H:%M:%S}",
        )

    @dp.message(F.text == "📥 ریستور")
    async def ask_restore(message, bot):
        if not is_admin(message.from_user.id):
            return
        state[message.from_user.id] = {"step": "restore"}
        await bot.send_message(message.chat.id, "فایل backup.zip را بفرست.")

    @dp.message(F.text == "📚 راهنما")
    async def help_text(message, bot):
        if not is_admin(message.from_user.id):
            return
        await bot.send_message(
            message.chat.id,
            "📚 راهنما\n"
            "• ساخت سشن: شماره → کد SMS → رمز (اگر 2FA دارد)\n"
            "• جوین/لیو: فرمت سهخطی، Delay رعایت میشود\n"
            "• بررسی: سشنهای خراب/تکراری پاک میشوند\n"
            "• بکاپ: فایل zip با هش تأیید میشود\n"
            "• ریستور: همان فایل zip را بفرست\n"
            "• /cancel: لغو عملیات جاری\n\n"
            "⚠️ self-bot غیررسمی است و خطر مسدود شدن اکانت دارد.",
        )

    @dp.message(F.document)
    async def handle_document(message, bot):
        if not is_admin(message.from_user.id):
            return
        doc = message.document
        name = getattr(doc, "file_name", "") or ""

        if not name.endswith(".zip"):
            await bot.send_message(message.chat.id, "فقط فایل .zip بفرست.")
            return

        status = await bot.send_message(message.chat.id, "📥 در حال ریستور...")
        path = "incoming_backup.zip"

        try:
            data = await bot.download_file(getattr(doc, "file_id", ""))
            with open(path, "wb") as handle:
                handle.write(data)

            imported = mgr.import_zip(path)
            await edit(status, f"✅ {imported} اکانت ریستور شد.")
        except Exception as exc:  # noqa: BLE001
            await edit(status, f"❌ ریستور نشد:\n{exc}")
        finally:
            if os.path.exists(path):
                os.remove(path)
            state.pop(message.from_user.id, None)

    @dp.message(F.text)
    async def handle_state(message, bot):
        uid = message.from_user.id
        if not is_admin(uid) or uid not in state:
            return

        current = state[uid]
        step = current.get("step")
        text = (message.text or "").strip()

        # ---- ساخت سشن: شماره ----
        if step == "phone":
            phone = to_english_digits(text)
            state[uid] = {"step": "code", "phone": phone}
            result = await mgr.request_code(phone)
            if not result.ok:
                await bot.send_message(message.chat.id, f"❌ {result.message}")
                state.pop(uid, None)
                return
            await bot.send_message(
                message.chat.id, f"📨 کد به {phone} ارسال شد. کد را بفرست."
            )

        # ---- ساخت سشن: کد ----
        elif step == "code":
            result = await mgr.submit_code(current["phone"], to_english_digits(text))
            if result.needs_password:
                state[uid] = {"step": "password", "phone": current["phone"]}
                await bot.send_message(message.chat.id, "🔐 رمز دومرحلهای را بفرست.")
                return
            if not result.ok:
                await bot.send_message(message.chat.id, f"❌ {result.message}")
            else:
                await bot.send_message(
                    message.chat.id, f"🎉 سشن {current['phone']} ساخته و ذخیره شد."
                )
            state.pop(uid, None)

        # ---- جوین / لیو ----
        elif step in {"join", "leave"}:
            parts = text.split("\n")
            if len(parts) != 3 or not parts[1].strip().isdigit():
                await bot.send_message(
                    message.chat.id, "فرمت اشتباه است:\n[عملیات]\n[تعداد]\n[لینک]"
                )
                return
            count = int(parts[1].strip())
            link = parts[2].strip()
            accounts = mgr.list_accounts()[:count]
            if len(accounts) < count:
                await bot.send_message(
                    message.chat.id, f"⚠️ فقط {len(accounts)} اکانت موجود است."
                )
            state.pop(uid, None)
            await run_bulk(bot, message.chat.id, accounts, "جوین" if step == "join" else "لیو", link)

        # ---- Delay ----
        elif step == "delay":
            digits = to_english_digits(text)
            if digits.isdigit() and int(digits) > 0:
                DELAY["seconds"] = float(digits)
                await bot.send_message(message.chat.id, f"✅ Delay = {digits} ثانیه")
            else:
                await bot.send_message(message.chat.id, "عدد معتبر بفرست.")
            state.pop(uid, None)

        # ---- رمز دومرحلهای ----
        elif step == "password":
            await bot.send_message(
                message.chat.id,
                "رمز دومرحلهای فعلاً از طریق CLI پشتیبانی میشود: badking login",
            )
            state.pop(uid, None)

    return dp


async def run_bulk(bot, chat_id: int, accounts, action: str, link: str) -> None:
    """جوین/لیو دستهجمعی با Delay و گزارش پیشرفت."""
    status = await bot.send_message(chat_id, f"🔄 {action} {len(accounts)} اکانت...")
    done, failed = 0, 0

    for index, acc in enumerate(accounts, 1):
        session = mgr.get(acc.key)
        if not session:
            failed += 1
            continue
        try:
            async with SelfBot(session=session) as sb:
                if action == "جوین":
                    await sb.join_by_link(link)
                else:
                    preview = await sb.get_group_preview(link)
                    if preview["id"]:
                        await sb.leave_by_id(preview["id"])
            done += 1
        except Exception:  # noqa: BLE001
            failed += 1

        if index % 5 == 0:
            await edit(status, f"🔄 {action}: {index}/{len(accounts)}")

        await asyncio.sleep(DELAY["seconds"])

    await edit(status, f"✅ {action} تمام شد\n• موفق: {done}\n• ناموفق: {failed}")


async def main() -> None:
    token = os.environ.get("BADKING_TOKEN")
    if not token:
        print("لطفاً BADKING_TOKEN را تنظیم کن.")
        return

    bot = Bot(token)
    dp = build_dispatcher()

    print("پنل کنترل سشن BADKING")
    print(f"  اکانتهای فعلی: {mgr.count()}")
    print(f"  فایل سشن: {SESSION_FILE}")
    await bot.polling(dp)


if __name__ == "__main__":
    asyncio.run(main())
