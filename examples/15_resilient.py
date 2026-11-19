"""ربات مقاوم: همه چیز با هم.

هدف: رباتی که در شرایط بد هم کار می‌کند.

    python 15_resilient.py

این نمونه نشان می‌دهد چطور صف، مدارشکن، تلاش مجدد، و مدیریت خطا
با هم کار می‌کنند.
"""

import asyncio
import logging
import os

from badking import (
    BADKINGError,
    Bot,
    CircuitBreaker,
    CircuitOpenError,
    F,
    FloodWaitError,
    NetworkError,
    RateLimitError,
    RequestQueue,
    ResilientCaller,
    RetryPolicy,
    UnauthorizedError,
    format_exception,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("bot")


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    # ---------- زیرساخت تاب‌آوری ----------
    caller = ResilientCaller(
        queue=RequestQueue(concurrency=5, rate=20.0, max_pending=100),
        breaker=CircuitBreaker(failure_threshold=5, cooldown=30.0),
        policy=RetryPolicy(
            attempts=3,
            base_delay=0.5,
            max_delay=8.0,
            on_retry=lambda n, exc, delay: log.warning(
                "تلاش %d شکست خورد (%s)، %.1f ثانیه بعد دوباره",
                n, type(exc).__name__, delay,
            ),
        ),
    )

    # ---------- ارسال ایمن ----------
    async def safe_send(chat_id: int, text: str) -> bool:
        """پیام می‌فرستد و هر خطایی را مدیریت می‌کند. True یعنی موفق."""
        try:
            await caller(bot.send_message, chat_id, text)
            return True

        except FloodWaitError as exc:
            # سرور صریحاً گفته چند ثانیه صبر کن
            log.warning("flood wait: %.0f ثانیه", exc.retry_after or 0)
            await asyncio.sleep(exc.retry_after or 30)
            return False

        except RateLimitError:
            log.warning("محدودیت نرخ، رد شد")
            return False

        except CircuitOpenError:
            # سرور پایین است — تلاش بیشتر فقط وضع را بدتر می‌کند
            log.error("مدارشکن باز است، ارسال متوقف شد")
            return False

        except UnauthorizedError:
            # توکن باطل شده — تلاش مجدد بی‌فایده است
            log.critical("توکن نامعتبر. ربات باید متوقف شود.")
            raise

        except NetworkError as exc:
            log.error("شبکه: %s", exc.hint)
            return False

        except BADKINGError as exc:
            log.error("خطای بله:\n%s", format_exception(exc))
            return False

    # ---------- هندلرها ----------
    @bot.on_message(F.text == "/start")
    async def start(message):
        await safe_send(message.chat.id, "سلام! ربات مقاوم روشن است.")

    @bot.on_message(F.text == "/status")
    async def status(message):
        await safe_send(
            message.chat.id,
            f"وضعیت:\n"
            f"  مدارشکن: {caller.breaker.state.value}\n"
            f"  در صف: {caller.queue.pending}\n"
            f"  خطاهای پیاپی: {caller.breaker._failures}",
        )

    @bot.on_message(F.text == "/broadcast")
    async def broadcast(message):
        """ارسال انبوه با مدیریت خطا."""
        text = message.text.replace("/broadcast", "").strip()
        if not text:
            await safe_send(message.chat.id, "/broadcast متن")
            return

        # شناسه‌های کاربران را از جایی بگیر
        user_ids = [123456789, 987654321]

        results = await asyncio.gather(
            *[safe_send(uid, text) for uid in user_ids],
            return_exceptions=True,
        )

        sent = sum(1 for r in results if r is True)
        failed = len(results) - sent

        await safe_send(
            message.chat.id,
            f"ارسال شد: {sent}\nناموفق: {failed}",
        )

    @bot.on_message(F.text)
    async def echo(message):
        await safe_send(message.chat.id, message.text)

    # ---------- اجرا با خاموشی ایمن ----------
    log.info("ربات روشن شد")
    try:
        await bot.run()
    except KeyboardInterrupt:
        log.info("خاموشی...")
    finally:
        # فرصت بده تا کارهای در جریان تمام شوند
        log.info("صبر برای %d کار در جریان", caller.queue.pending)
        await asyncio.sleep(1)
        log.info("خاموش شد")


if __name__ == "__main__":
    asyncio.run(main())
