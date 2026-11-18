"""اجرای ربات فروشگاه با لاگ زنده (برای تست دکمهها در بله واقعی)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from badking import Bot  # noqa: E402
from shop_bot import build_dispatcher  # noqa: E402


def read_token() -> str | None:
    for p in (ROOT / ".env", ROOT / "mybot" / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.startswith("BADKING_TOKEN="):
                    return line.split("=", 1)[1].strip()
    return None


async def main() -> None:
    token = os.environ.get("BADKING_TOKEN") or read_token()
    if not token:
        print("توکن پیدا نشد")
        return
    bot = Bot(token)
    me = await bot.get_me()
    print(f"فروشگاه زنده شد: @{me.username}", flush=True)

    dp = build_dispatcher()

    async def log_mw(update, data, next_call):
        obj = update.callback_query or update.effective_message
        print(f"📥 {update.kind}: {(getattr(obj, 'data', None) or getattr(obj, 'content', '') or '')[:40]}", flush=True)
        r = await next_call(update, data)
        print("📤 جواب ارسال شد", flush=True)
        return r

    dp.register_middleware(log_mw)

    print("در حال گوش دادن... (Ctrl+C)", flush=True)
    await bot.polling(dp)


if __name__ == "__main__":
    asyncio.run(main())
