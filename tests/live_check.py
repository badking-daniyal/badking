"""تست زنده با توکن واقعی — getMe و خواندن آپدیتها.

اجرا: py tests/live_check.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking import Bot  # noqa: E402


def read_token() -> str | None:
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("BADKING_TOKEN="):
                return line.split("=", 1)[1].strip()
    return None


async def main() -> None:
    token = read_token()
    if not token:
        print("توکن پیدا نشد")
        return
    bot = Bot(token)
    print("در حال تماس با بله...")
    try:
        me = await bot.get_me()
        print(f"✅ توکن معتبر است")
        print(f"   نام ربات: {me.first_name}")
        print(f"   یوزرنیم: @{me.username}")
        print(f"   آیدی: {me.id}")
    except Exception as e:
        print(f"❌ خطا: {type(e).__name__}: {e}")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
