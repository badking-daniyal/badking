"""تستهای فاز ۸: Hybrid ایزوله + لایه سازگاری."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking.compat import Application, Bot as CompatBot, Dispatcher as CompatDispatcher, F as CompatF  # noqa: E402
from badking.hybrid import HybridDisabledError, HybridPlugin, hybrid_warning  # noqa: E402


def test_hybrid_disabled_by_default():
    plugin = HybridPlugin()
    assert plugin.enabled is False
    try:
        asyncio.get_event_loop().run_until_complete(plugin.activate())
        assert False, "باید خطا میداد"
    except HybridDisabledError:
        pass


def test_hybrid_requires_ack():
    plugin = HybridPlugin(enabled=True, ack_risk=False)
    assert plugin.enabled is False
    plugin2 = HybridPlugin(enabled=True, ack_risk=True)
    assert plugin2.enabled is True
    assert plugin2.lane == "selfbot"


def test_hybrid_warning():
    w = hybrid_warning()
    assert "SELF-BOT" in w
    assert "keyring" in w


def test_compat_aliases():
    assert CompatBot.__name__ == "Bot"
    assert CompatDispatcher.__name__ == "Dispatcher"
    assert (CompatF.text == "/start")


def test_compat_application_builder():
    app = Application.builder().token("1:TEST").build()
    assert isinstance(app.bot, CompatBot)
    assert app.bot.token == "1:TEST"
