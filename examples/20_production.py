"""ربات تولیدی: ساختار کامل، آماده deploy.

هدف: الگویی که در تولید واقعاً کار می‌کند.

    python 20_production.py

ساختار:
    config.py     ← تنظیمات از محیط
    handlers/     ← هندلرها
    main.py       ← این فایل
    Dockerfile    ← deploy
"""

import asyncio
import logging
import os
import signal
import sys
from dataclasses import dataclass

from badking import (
    BADKINGError,
    Bot,
    CircuitBreaker,
    F,
    Health,
    Metrics,
    RequestQueue,
    ResilientCaller,
    RetryPolicy,
    format_exception,
)


# ---------- تنظیمات ----------

@dataclass
class Config:
    """همه تنظیمات از محیط. هیچ مقدار حساسی در کد نیست."""

    token: str
    admin_id: int
    log_level: str = "INFO"
    concurrency: int = 5
    rate: float = 20.0

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ.get("BADKING_TOKEN")
        if not token:
            raise SystemExit("BADKING_TOKEN تنظیم نشده.")

        admin = os.environ.get("ADMIN_ID")
        if not admin or not admin.isdigit():
            raise SystemExit("ADMIN_ID تنظیم نشده یا عدد نیست.")

        return cls(
            token=token,
            admin_id=int(admin),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            concurrency=int(os.environ.get("CONCURRENCY", "5")),
            rate=float(os.environ.get("RATE", "20")),
        )


# ---------- لاگ ----------

def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stdout,
    )


log = logging.getLogger("badking.app")


# ---------- برنامه ----------

class Application:
    """ربات با همه زیرساخت لازم."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.bot = Bot(config.token)
        self.metrics = Metrics()
        self.health = Health()
        self._shutdown = asyncio.Event()

        self.caller = ResilientCaller(
            queue=RequestQueue(
                concurrency=config.concurrency,
                rate=config.rate,
            ),
            breaker=CircuitBreaker(failure_threshold=5, cooldown=30.0),
            policy=RetryPolicy(attempts=3, base_delay=0.5),
        )

        self._register_handlers()
        self._register_middleware()

    # ---------- میان‌افزار ----------

    def _register_middleware(self) -> None:
        @self.bot.middleware(priority=100)
        async def observe(handler, event, data):
            """همه پیام‌ها را می‌شمارد و زمان می‌گیرد."""
            self.metrics.inc("messages_total")
            try:
                return await handler(event, data)
            except BADKINGError as exc:
                self.metrics.inc("errors_total")
                log.error("خطا:\n%s", format_exception(exc))
                raise

    # ---------- هندلرها ----------

    def _register_handlers(self) -> None:
        bot = self.bot

        @bot.on_message(F.text == "/start")
        async def start(message):
            self.metrics.inc("starts_total")
            await self.caller(
                bot.send_message,
                message.chat.id,
                "سلام! ربات آماده است.",
            )

        @bot.on_message(F.text == "/health")
        async def health(message):
            if message.from_user.id != self.config.admin_id:
                return

            status = self.health.check()
            await self.caller(
                bot.send_message,
                message.chat.id,
                f"سلامت: {status}\n"
                f"مدارشکن: {self.caller.breaker.state.value}\n"
                f"در صف: {self.caller.queue.pending}\n"
                f"پیام‌ها: {self.metrics.get('messages_total', 0)}",
            )

        @bot.on_message(F.text == "/metrics")
        async def metrics(message):
            if message.from_user.id != self.config.admin_id:
                return
            await self.caller(
                bot.send_message,
                message.chat.id,
                self.metrics.render_prometheus(),
            )

        @bot.on_message(F.text == "/stop")
        async def stop(message):
            if message.from_user.id != self.config.admin_id:
                return
            await self.caller(
                bot.send_message,
                message.chat.id,
                "خاموش می‌شوم.",
            )
            self._shutdown.set()

        @bot.on_message(F.text)
        async def echo(message):
            await self.caller(
                bot.send_message,
                message.chat.id,
                message.text,
            )

    # ---------- اجرا ----------

    async def run(self) -> None:
        """اجرا با خاموشی ایمن.

        Ctrl+C یا SIGTERM → کارهای در جریان تمام می‌شوند، بعد خروج.
        """
        loop = asyncio.get_event_loop()

        # SIGTERM را به رویداد خاموشی وصل کن (برای Docker و systemd)
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._shutdown.set)
            except NotImplementedError:
                # ویندوز add_signal_handler ندارد — KeyboardInterrupt کار می‌کند
                pass

        log.info("ربات روشن شد (admin=%d)", self.config.admin_id)
        self.health.mark_ready()

        bot_task = asyncio.ensure_future(self.bot.run())
        shutdown_task = asyncio.ensure_future(self._shutdown.wait())

        done, pending = await asyncio.wait(
            {bot_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # ---------- خاموشی ایمن ----------
        log.info("خاموشی آغاز شد")

        for task in pending:
            task.cancel()

        if bot_task in done and not bot_task.cancelled():
            exc = bot_task.exception()
            if exc:
                log.error("ربات با خطا متوقف شد:\n%s", format_exception(exc))

        # فرصت بده تا صف خالی شود
        deadline = asyncio.get_event_loop().time() + 10
        while self.caller.queue.pending > 0:
            if asyncio.get_event_loop().time() > deadline:
                log.warning("مهلت خاموشی تمام شد، %d کار رها شد", self.caller.queue.pending)
                break
            await asyncio.sleep(0.1)

        self.health.mark_stopped()
        log.info("خاموش شد")


# ---------- نقطه ورود ----------

async def main() -> None:
    config = Config.from_env()
    setup_logging(config.log_level)

    app = Application(config)

    try:
        await app.run()
    except KeyboardInterrupt:
        log.info("متوقف شد")


if __name__ == "__main__":
    asyncio.run(main())
