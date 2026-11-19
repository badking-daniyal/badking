"""CLI جادویی BADKING — badking new / run / dry-run.

برای کسی که کد بلد نیست: چند سوال میپرسد و یک ربات کامل تحویل میدهد.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TEMPLATE = '''"""ربات BADKING — ساختهشده توسط `badking new`"""

import asyncio
import os
from badking import Bot, Dispatcher, F

bot = Bot(os.environ.get("BADKING_TOKEN", "TOKEN"))
dp = Dispatcher()

@dp.message(F.text == "/start")
async def start(message, bot):
    await bot.send_message(message.chat.id, "{greeting}")

@dp.message()
async def echo(message, bot):
    if message.text:
        await bot.send_message(message.chat.id, f"شما گفتید: {{message.text}}")

if __name__ == "__main__":
    asyncio.run(bot.polling(dp))
'''

FLOW_TEMPLATE = '''{
  "start": "welcome",
  "steps": {
    "welcome": {"type": "message", "text": "سلام! به ربات من خوش آمدید.", "next": "ask_name"},
    "ask_name": {"type": "ask", "text": "نامت چیه؟", "save": "name", "next": "done"},
    "done": {"type": "message", "text": "خوش آمدی {name}!"}
  }
}
'''


def cmd_new(args: argparse.Namespace) -> int:
    name = args.name
    folder = Path(name)
    if folder.exists():
        print(f"پوشه {name} از قبل وجود دارد.")
        return 1
    folder.mkdir(parents=True)
    greeting = args.greeting or "سلام! من ربات BADKING هستم 🤖"
    (folder / "bot.py").write_text(TEMPLATE.format(greeting=greeting), encoding="utf-8")
    (folder / "flow.json").write_text(FLOW_TEMPLATE, encoding="utf-8")
    (folder / ".env.example").write_text("BADKING_TOKEN=123456789:TOKEN\n", encoding="utf-8")
    (folder / "README.md").write_text(
        f"# {name}\n\nربات ساختهشده با BADKING.\n\n"
        "1. توکن را از @botfather بگیر.\n"
        "2. BADKING_TOKEN را تنظیم کن.\n"
        "3. `python bot.py`\n\n"
        "برای ویرایش جریان بدون کد، flow.json را عوض کن.\n",
        encoding="utf-8",
    )
    print(f"ربات '{name}' ساخته شد ✅")
    print(f"  → {folder.resolve()}")
    print("گام بعدی: توکن را تنظیم کن و `python bot.py` را اجرا کن.")
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    """اجرای جریان بدون توکن و بدون شبکه."""
    from ..flows import Flow

    path = Path(args.flow)
    if not path.exists():
        print(f"فایل {path} پیدا نشد.")
        return 1
    flow = Flow.from_json(path)
    session = flow.start_session()
    for msg in session.messages:
        print("ربات:", msg)
    while session.waiting_for and not session.ended:
        answer = input("شما: ")
        session = flow.handle(session.waiting_for, answer, session.data)
        for msg in session.messages:
            print("ربات:", msg)
    print("--- پایان جریان ---")
    return 0


def cmd_codegen(args: argparse.Namespace) -> int:
    from ..flows import Flow

    flow = Flow.from_json(args.flow)
    code = flow.to_python()
    out = Path(args.output or "generated_bot.py")
    out.write_text(code, encoding="utf-8")
    print(f"کد به {out} نوشته شد.")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    """توکن را از کاربر میپرسد و در فایل .env ذخیره میکند (بدون کدنویسی)."""
    from ..security import Secrets

    token = args.token or input("توکن بازو را از @botfather بگیر و اینجا بچسبان: ").strip()
    if not token or ":" not in token:
        print("توکن نامعتبر است. فرمت درست: 123456789:abcdef...")
        return 1
    env = Path(".env")
    env.write_text(f"BADKING_TOKEN={token}\n", encoding="utf-8")
    print(f"توکن ذخیره شد ✅ → {env.resolve()}")
    print(f"نمایش ایمن: {Secrets.mask(token)}")
    print("حالا با `badking run` ربات را روشن کن.")
    return 0


def _load_env() -> None:
    """خواندن فایل .env به داخل متغیرهای محیطی (بدون وابستگی)."""
    import os
    env = Path(".env")
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def cmd_run(args: argparse.Namespace) -> int:
    """ربات را با توکن ذخیرهشده روشن میکند (long polling)."""
    import asyncio
    _load_env()
    token = __import__("os").environ.get("BADKING_TOKEN")
    if not token or token == "TOKEN":
        print("توکن پیدا نشد. اول `badking setup` را اجرا کن.")
        return 1
    from ..core.bot import Bot
    from ..core.dispatcher import Dispatcher
    from ..filters.magic import F

    bot = Bot(token)
    dp = Dispatcher()

    async def log_update(update, data, next_call):
        print(f"📥 آپدیت: {update.kind}", flush=True)
        result = await next_call(update, data)
        print("📤 جواب ارسال شد", flush=True)
        return result

    dp.register_middleware(log_update)

    @dp.message(F.text == "/start")
    async def start(message, bot):
        await bot.send_message(message.chat.id, "سلام! ربات BADKING روشن است 🤖")

    @dp.message()
    async def echo(message, bot):
        if message.text:
            await bot.send_message(message.chat.id, f"شما گفتید: {message.text}")

    print("ربات در حال اجرا... (Ctrl+C برای توقف)")
    try:
        asyncio.run(bot.polling(dp))
    except KeyboardInterrupt:
        print("\nربات متوقف شد.")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    """ورود self-bot با شماره و کد SMS."""
    import asyncio

    from badking.hybrid import SelfBot

    print("⚠️  حالت self-bot — با اکانت اصلی وارد نشو.")

    async def run() -> int:
        bot = SelfBot(
            session=args.session,
            phone=args.phone,
            password=args.password,
        )
        try:
            await bot.connect()
            me = await bot.get_me()
            print(f"✅ وارد شدی: {me}")
            print(f"   session ذخیره شد در: {args.session}")
            return 0
        finally:
            await bot.close()

    return asyncio.get_event_loop().run_until_complete(run())


def cmd_accounts(args: argparse.Namespace) -> int:
    """لیست اکانت‌های ذخیره‌شده."""
    from badking.hybrid import SessionStore

    store = SessionStore(args.session, password=args.password)
    accounts = store.list_accounts()
    if not accounts:
        print("هیچ اکانتی ذخیره نشده. اول `badking login` بزن.")
        return 0
    for acc in accounts:
        mark = "✅" if acc["valid"] else "⚠️ "
        print(f"{mark} {acc['key']}  {acc['name']}  {acc['phone']}")
    return 0


def cmd_selfbot(args: argparse.Namespace) -> int:
    """اجرای یک اسکریپت self-bot با session آماده."""
    import runpy

    from badking.hybrid import SessionStore

    store = SessionStore(args.session, password=args.password)
    session = store.get()
    if session is None:
        print("session پیدا نشد. اول `badking login` بزن.")
        return 1
    os.environ["BADKING_SELFBOT_SESSION"] = args.session
    runpy.run_path(args.script, run_name="__main__")
    return 0


def cmd_rpc(args: argparse.Namespace) -> int:
    """لیست RPC های موجود."""
    import json

    from badking.hybrid import registry

    if args.json:
        data = {
            name: {
                "req": registry.get(name).req,
                "resp": registry.get(name).resp,
                "doc": registry.get(name).doc,
                "dangerous": registry.get(name).dangerous,
            }
            for name in registry.names()
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.service:
        methods = registry.by_service().get(args.service, [])
        if not methods:
            print(f"سرویس ناشناخته: {args.service}")
            return 1
        for m in methods:
            spec = registry.get(f"{args.service}.{m}")
            flag = " ⚠️" if spec.dangerous else ""
            print(f"  {spec.full_name:32} {spec.doc}{flag}")
        return 0

    for service, methods in sorted(registry.by_service().items()):
        print(f"\n{service} ({len(methods)})")
        for m in methods:
            spec = registry.get(f"{service}.{m}")
            flag = " ⚠️" if spec.dangerous else ""
            print(f"  {m:28} {spec.doc}{flag}")
    print(f"\nمجموع: {len(registry.names())} متد")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="badking", description="BADKING — فریمورک ربات بله")
    sub = parser.add_subparsers(dest="cmd")

    p_new = sub.add_parser("new", help="ساخت ربات جدید")
    p_new.add_argument("name", help="نام پوشه ربات")
    p_new.add_argument("--greeting", help="پیام خوشآمدگویی")
    p_new.set_defaults(func=cmd_new)

    p_dry = sub.add_parser("dry-run", help="تست جریان بدون توکن")
    p_dry.add_argument("--flow", default="flow.json")
    p_dry.set_defaults(func=cmd_dry_run)

    p_code = sub.add_parser("codegen", help="تبدیل جریان به کد پایتون")
    p_code.add_argument("--flow", default="flow.json")
    p_code.add_argument("--output", default="generated_bot.py")
    p_code.set_defaults(func=cmd_codegen)

    p_setup = sub.add_parser("setup", help="ذخیره توکن بازو (قدم اول)")
    p_setup.add_argument("--token", help="توکن به جای ورودی تعاملی")
    p_setup.set_defaults(func=cmd_setup)

    p_run = sub.add_parser("run", help="روشن کردن ربات")
    p_run.set_defaults(func=cmd_run)

    p_login = sub.add_parser("login", help="ورود self-bot با شماره و کد SMS")
    p_login.add_argument("--phone", required=True, help="شماره تلفن (0912... یا +98912...)")
    p_login.add_argument("--session", default="badking.session", help="مسیر فایل session")
    p_login.add_argument("--password", help="رمز رمزنگاری فایل session")
    p_login.set_defaults(func=cmd_login)

    p_accounts = sub.add_parser("accounts", help="لیست اکانت‌های self-bot")
    p_accounts.add_argument("--session", default="badking.session")
    p_accounts.add_argument("--password")
    p_accounts.set_defaults(func=cmd_accounts)

    p_self = sub.add_parser("selfbot", help="اجرای اسکریپت self-bot")
    p_self.add_argument("script", help="فایل پایتون")
    p_self.add_argument("--session", default="badking.session")
    p_self.add_argument("--password")
    p_self.set_defaults(func=cmd_selfbot)

    p_rpc = sub.add_parser("rpc", help="لیست RPC های self-bot")
    p_rpc.add_argument("--service", help="فقط یک سرویس")
    p_rpc.add_argument("--json", action="store_true", help="خروجی JSON")
    p_rpc.set_defaults(func=cmd_rpc)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
