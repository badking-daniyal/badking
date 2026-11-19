"""سیستم افزونه — قابلیت اضافه کن بدون دست زدن به هسته.

    from badking.plugins import Plugin, PluginManager

    class StatsPlugin(Plugin):
        name = "stats"

        async def setup(self, bot):
            @bot.on_message(F.text == "/stats")
            async def stats(message):
                await message.reply(f"پیام‌ها: {self.state['count']}")

        async def on_message(self, message):
            self.state["count"] = self.state.get("count", 0) + 1

    manager = PluginManager()
    manager.register(StatsPlugin())
    await manager.setup_all(bot)

چرا افزونه: هر رباتی قابلیت‌هایی دارد که فقط برای همان ربات است. اگر
آن‌ها را در هسته بگذاری، هسته سنگین می‌شود. افزونه جدا می‌ماند، تست
جدا دارد، و می‌شود خاموشش کرد.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("badking.plugins")


class PluginError(Exception):
    """خطای افزونه."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message}\n  → {self.hint}" if self.hint else self.message


@dataclass
class Plugin:
    """پایه افزونه.

    هر افزونه سه چیز می‌تواند داشته باشد:

    - `setup(bot)` — یک بار موقع روشن شدن. هندلرها را ثبت کن.
    - `on_message(message)` — هر پیام. سبک نگهش دار.
    - `teardown()` — موقع خاموشی. اتصال‌ها را ببند.

    `state` دیکشنری آزاد برای داده خودت است.
    """

    name: str = ""
    """نام یکتا. اگر خالی باشد از نام کلاس استفاده می‌شود."""
    version: str = "1.0.0"
    enabled: bool = True
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            self.name = type(self).__name__

    async def setup(self, bot: Any) -> None:
        """یک بار موقع روشن شدن. هندلرها را اینجا ثبت کن."""

    async def teardown(self) -> None:
        """موقع خاموشی. منابع را آزاد کن."""

    async def on_message(self, message: Any) -> None:
        """هر پیام ورودی. اگر خطا بدهد، بقیه افزونه‌ها متوقف نمی‌شوند."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name} v{self.version}>"


class PluginManager:
    """مدیریت چرخه عمر افزونه‌ها.

        manager = PluginManager()
        manager.register(StatsPlugin())
        manager.register(LogPlugin())
        await manager.setup_all(bot)
        ...
        await manager.teardown_all()
    """

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        # list است نه set: ترتیب راه‌اندازی را باید نگه داریم تا موقع
        # خاموشی به ترتیب معکوس ببندیم. set ترتیب را از دست می‌دهد.
        self._setup_done: list[str] = []

    # ---------- ثبت ----------

    def register(self, plugin: Plugin) -> None:
        """افزونه را ثبت می‌کند. نام تکراری خطاست."""
        if not isinstance(plugin, Plugin):
            raise PluginError(
                f"{type(plugin).__name__} از Plugin ارث نمی‌برد",
                hint="کلاس را از badking.plugins.Plugin ارث بده.",
            )
        if plugin.name in self._plugins:
            raise PluginError(
                f"افزونه‌ای با نام {plugin.name!r} قبلاً ثبت شده",
                hint="نام یکتا بگذار، یا اول unregister کن.",
            )
        self._plugins[plugin.name] = plugin
        log.debug("افزونه ثبت شد: %s", plugin)

    def unregister(self, name: str) -> bool:
        """افزونه را حذف می‌کند. True یعنی بود."""
        plugin = self._plugins.pop(name, None)
        if name in self._setup_done:
            self._setup_done.remove(name)
        return plugin is not None

    def get(self, name: str) -> Plugin | None:
        """افزونه با این نام."""
        return self._plugins.get(name)

    def names(self) -> list[str]:
        """نام همه افزونه‌ها، به ترتیب ثبت."""
        return list(self._plugins)

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        return name in self._plugins

    # ---------- چرخه عمر ----------

    async def setup_all(self, bot: Any) -> None:
        """همه افزونه‌های فعال را راه می‌اندازد.

        اگر یکی خطا بدهد، بقیه راه می‌افتند و خطا لاگ می‌شود. یک افزونه
        شکسته نباید کل ربات را زمین بزند.
        """
        for name, plugin in self._plugins.items():
            if not plugin.enabled or name in self._setup_done:
                continue
            try:
                await plugin.setup(bot)
                self._setup_done.append(name)
                log.info("افزونه راه افتاد: %s", name)
            except Exception as exc:  # noqa: BLE001
                log.error("افزونه %s راه نیفتاد: %s", name, exc)

    async def teardown_all(self) -> None:
        """همه افزونه‌ها را می‌بندد، به ترتیب معکوس."""
        for name in reversed(list(self._setup_done)):
            plugin = self._plugins.get(name)
            if not plugin:
                continue
            try:
                await plugin.teardown()
                log.info("افزونه بسته شد: %s", name)
            except Exception as exc:  # noqa: BLE001
                log.error("بستن افزونه %s خطا داد: %s", name, exc)
        self._setup_done.clear()

    async def dispatch_message(self, message: Any) -> None:
        """پیام را به همه افزونه‌های فعال می‌دهد."""
        for plugin in self._plugins.values():
            if not plugin.enabled:
                continue
            try:
                await plugin.on_message(message)
            except Exception as exc:  # noqa: BLE001
                log.error("افزونه %s در پردازش پیام خطا داد: %s", plugin.name, exc)

    # ---------- کنترل ----------

    def enable(self, name: str) -> None:
        """روشن کردن افزونه."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.enabled = True

    def disable(self, name: str) -> None:
        """خاموش کردن بدون حذف."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.enabled = False

    def status(self) -> dict[str, dict[str, Any]]:
        """وضعیت همه افزونه‌ها."""
        return {
            name: {
                "version": plugin.version,
                "enabled": plugin.enabled,
                "setup": name in self._setup_done,
            }
            for name, plugin in self._plugins.items()
        }


# ---------- افزونه‌های آماده ----------

class StatsPlugin(Plugin):
    """شمارش پیام و کاربر.

        manager.register(StatsPlugin())
        ...
        stats = manager.get("StatsPlugin").state
        print(stats["messages"], len(stats["users"]))
    """

    name = "stats"

    async def setup(self, bot: Any) -> None:
        self.state.setdefault("messages", 0)
        self.state.setdefault("users", set())

    async def on_message(self, message: Any) -> None:
        self.state["messages"] = self.state.get("messages", 0) + 1
        user = getattr(message, "from_user", None)
        if user:
            self.state.setdefault("users", set()).add(user.id)


class LogPlugin(Plugin):
    """لاگ هر پیام. برای دیباگ."""

    name = "log"

    async def on_message(self, message: Any) -> None:
        user = getattr(message, "from_user", None)
        name = getattr(user, "first_name", "?") if user else "?"
        text = (getattr(message, "text", "") or "")[:60]
        log.info("%s: %s", name, text)


class RatePlugin(Plugin):
    """محدودیت نرخ ساده: هر کاربر حداکثر n پیام در پنجره."""

    name = "rate"

    def __init__(self, max_messages: int = 10, window: float = 10.0) -> None:
        super().__init__()
        self.max_messages = max_messages
        self.window = window
        self.state["hits"] = {}

    async def on_message(self, message: Any) -> None:
        import time

        user = getattr(message, "from_user", None)
        if not user:
            return

        now = time.monotonic()
        hits = self.state["hits"].setdefault(user.id, [])
        cutoff = now - self.window
        recent = [t for t in hits if t > cutoff]
        recent.append(now)
        self.state["hits"][user.id] = recent

        if len(recent) > self.max_messages:
            self.state["blocked"] = self.state.get("blocked", 0) + 1


__all__ = [
    "LogPlugin",
    "Plugin",
    "PluginError",
    "PluginManager",
    "RatePlugin",
    "StatsPlugin",
]
