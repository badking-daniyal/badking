"""تست سیستم افزونه و بومی‌سازی."""

from __future__ import annotations

import asyncio

import pytest

from badking.i18n import (
    Catalog,
    TranslationError,
    Translator,
    default_translator,
    en,
    fa,
)
from badking.plugins import (
    LogPlugin,
    Plugin,
    PluginError,
    PluginManager,
    RatePlugin,
    StatsPlugin,
)


# ---------- افزونه ----------

class TestPlugin:
    def test_name_defaults_to_class(self):
        class MyPlugin(Plugin):
            pass

        assert MyPlugin().name == "MyPlugin"

    def test_explicit_name(self):
        assert Plugin(name="custom").name == "custom"

    def test_repr(self):
        assert "v1.0.0" in repr(Plugin(name="x"))

    def test_enabled_by_default(self):
        assert Plugin(name="x").enabled is True

    def test_state_is_per_instance(self):
        a, b = Plugin(name="a"), Plugin(name="b")
        a.state["x"] = 1
        assert "x" not in b.state


class TestPluginManager:
    def test_register(self):
        m = PluginManager()
        m.register(Plugin(name="a"))
        assert len(m) == 1
        assert "a" in m
        assert m.names() == ["a"]

    def test_register_rejects_non_plugin(self):
        m = PluginManager()
        with pytest.raises(PluginError) as info:
            m.register(object())  # type: ignore[arg-type]
        assert "ارث" in str(info.value)

    def test_duplicate_name_rejected(self):
        m = PluginManager()
        m.register(Plugin(name="a"))
        with pytest.raises(PluginError) as info:
            m.register(Plugin(name="a"))
        assert "قبلاً ثبت شده" in str(info.value)

    def test_unregister(self):
        m = PluginManager()
        m.register(Plugin(name="a"))
        assert m.unregister("a") is True
        assert m.unregister("a") is False
        assert len(m) == 0

    def test_get(self):
        m = PluginManager()
        plugin = Plugin(name="a")
        m.register(plugin)
        assert m.get("a") is plugin
        assert m.get("nope") is None

    def test_setup_all_calls_setup(self):
        called = []

        class P(Plugin):
            async def setup(self, bot):
                called.append(bot)

        m = PluginManager()
        m.register(P(name="p"))
        asyncio.get_event_loop().run_until_complete(m.setup_all("BOT"))
        assert called == ["BOT"]

    def test_setup_skips_disabled(self):
        called = []

        class P(Plugin):
            async def setup(self, bot):
                called.append(1)

        m = PluginManager()
        plugin = P(name="p")
        plugin.enabled = False
        m.register(plugin)
        asyncio.get_event_loop().run_until_complete(m.setup_all("BOT"))
        assert called == []

    def test_setup_does_not_run_twice(self):
        called = []

        class P(Plugin):
            async def setup(self, bot):
                called.append(1)

        m = PluginManager()
        m.register(P(name="p"))
        loop = asyncio.get_event_loop()
        loop.run_until_complete(m.setup_all("BOT"))
        loop.run_until_complete(m.setup_all("BOT"))
        assert len(called) == 1

    def test_broken_plugin_does_not_stop_others(self):
        called = []

        class Broken(Plugin):
            async def setup(self, bot):
                raise RuntimeError("شکست")

        class Good(Plugin):
            async def setup(self, bot):
                called.append(1)

        m = PluginManager()
        m.register(Broken(name="broken"))
        m.register(Good(name="good"))
        asyncio.get_event_loop().run_until_complete(m.setup_all("BOT"))
        assert called == [1]

    def test_teardown_all(self):
        closed = []

        class P(Plugin):
            async def teardown(self):
                closed.append(self.name)

        m = PluginManager()
        m.register(P(name="a"))
        m.register(P(name="b"))
        loop = asyncio.get_event_loop()
        loop.run_until_complete(m.setup_all("BOT"))
        loop.run_until_complete(m.teardown_all())
        # ترتیب معکوس
        assert closed == ["b", "a"]

    def test_dispatch_message(self):
        seen = []

        class P(Plugin):
            async def on_message(self, message):
                seen.append(message)

        m = PluginManager()
        m.register(P(name="p"))
        asyncio.get_event_loop().run_until_complete(m.dispatch_message("MSG"))
        assert seen == ["MSG"]

    def test_dispatch_skips_disabled(self):
        seen = []

        class P(Plugin):
            async def on_message(self, message):
                seen.append(message)

        m = PluginManager()
        plugin = P(name="p")
        plugin.enabled = False
        m.register(plugin)
        asyncio.get_event_loop().run_until_complete(m.dispatch_message("MSG"))
        assert seen == []

    def test_dispatch_isolates_errors(self):
        seen = []

        class Broken(Plugin):
            async def on_message(self, message):
                raise RuntimeError("x")

        class Good(Plugin):
            async def on_message(self, message):
                seen.append(1)

        m = PluginManager()
        m.register(Broken(name="broken"))
        m.register(Good(name="good"))
        asyncio.get_event_loop().run_until_complete(m.dispatch_message("MSG"))
        assert seen == [1]

    def test_enable_disable(self):
        m = PluginManager()
        m.register(Plugin(name="a"))
        m.disable("a")
        assert m.get("a").enabled is False
        m.enable("a")
        assert m.get("a").enabled is True

    def test_status(self):
        m = PluginManager()
        m.register(Plugin(name="a", version="2.0.0"))
        status = m.status()
        assert status["a"]["version"] == "2.0.0"
        assert status["a"]["enabled"] is True
        assert status["a"]["setup"] is False


class TestBuiltinPlugins:
    def test_stats_counts(self):
        plugin = StatsPlugin()

        class User:
            id = 42

        class Message:
            from_user = User()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(plugin.setup(None))
        loop.run_until_complete(plugin.on_message(Message()))
        loop.run_until_complete(plugin.on_message(Message()))

        assert plugin.state["messages"] == 2
        assert 42 in plugin.state["users"]

    def test_stats_handles_no_user(self):
        plugin = StatsPlugin()

        class Message:
            from_user = None

        loop = asyncio.get_event_loop()
        loop.run_until_complete(plugin.setup(None))
        loop.run_until_complete(plugin.on_message(Message()))
        assert plugin.state["messages"] == 1

    def test_log_plugin(self):
        plugin = LogPlugin()

        class User:
            first_name = "دانیال"

        class Message:
            from_user = User()
            text = "سلام"

        asyncio.get_event_loop().run_until_complete(plugin.on_message(Message()))

    def test_rate_plugin_blocks_after_limit(self):
        plugin = RatePlugin(max_messages=2, window=10.0)

        class User:
            id = 1

        class Message:
            from_user = User()

        loop = asyncio.get_event_loop()
        for _ in range(5):
            loop.run_until_complete(plugin.on_message(Message()))

        assert plugin.state["blocked"] >= 1


# ---------- بومی‌سازی ----------

class TestCatalog:
    def test_get(self):
        c = Catalog("fa", {"a": "الف"})
        assert c.get("a") == "الف"
        assert c.get("b") is None

    def test_contains(self):
        c = Catalog("fa", {"a": "الف"})
        assert "a" in c
        assert "b" not in c

    def test_len(self):
        assert len(Catalog("fa", {"a": "1", "b": "2"})) == 2


class TestTranslator:
    def test_basic(self):
        t = Translator(Catalog("fa", {"hi": "سلام"}), default="fa")
        assert t("hi") == "سلام"

    def test_params(self):
        t = Translator(Catalog("fa", {"hi": "سلام {name}"}), default="fa")
        assert t("hi", name="دانیال") == "سلام دانیال"

    def test_language_switch(self):
        t = Translator(
            Catalog("fa", {"hi": "سلام"}),
            Catalog("en", {"hi": "Hello"}),
            default="fa",
        )
        assert t("hi", lang="en") == "Hello"
        assert t("hi", lang="fa") == "سلام"

    def test_fallback_to_default(self):
        t = Translator(
            Catalog("fa", {"a": "الف", "b": "ب"}),
            Catalog("en", {"a": "A"}),
            default="fa",
        )
        # b در en نیست → از fa می‌آید
        assert t("b", lang="en") == "ب"

    def test_unknown_language_falls_back(self):
        t = Translator(Catalog("fa", {"a": "الف"}), default="fa")
        assert t("a", lang="de") == "الف"

    def test_missing_key_returns_key(self):
        t = Translator(Catalog("fa", {}), default="fa")
        assert t("nope") == "nope"

    def test_missing_param_raises(self):
        t = Translator(Catalog("fa", {"hi": "سلام {name}"}), default="fa")
        with pytest.raises(TranslationError) as info:
            t("hi")
        assert "name" in str(info.value)

    def test_bad_format_raises(self):
        t = Translator(Catalog("fa", {"bad": "سلام {name"}), default="fa")
        with pytest.raises(TranslationError):
            t("bad", name="x")

    def test_languages(self):
        t = Translator(Catalog("fa", {}), Catalog("en", {}), default="fa")
        assert t.languages == ["fa", "en"]

    def test_add_catalog(self):
        t = Translator(Catalog("fa", {"a": "الف"}), default="fa")
        t.add(Catalog("ar", {"a": "ألف"}))
        assert t("a", lang="ar") == "ألف"

    def test_has(self):
        t = Translator(Catalog("fa", {"a": "الف"}), default="fa")
        assert t.has("a") is True
        assert t.has("b") is False

    def test_missing_keys(self):
        t = Translator(
            Catalog("fa", {"a": "1", "b": "2", "c": "3"}),
            Catalog("en", {"a": "1"}),
            default="fa",
        )
        assert set(t.missing("en")) == {"b", "c"}

    def test_default_language_required(self):
        with pytest.raises(TranslationError):
            Translator(Catalog("en", {}), default="fa")

    def test_default_translator(self):
        t = default_translator()
        assert t("welcome", name="دانیال") == "سلام دانیال!"
        assert t("welcome", name="Danial", lang="en") == "Hello Danial!"


class TestBuiltinCatalogs:
    def test_same_keys(self):
        """فارسی و انگلیسی باید همان کلیدها را داشته باشند."""
        missing_in_en = set(fa.strings) - set(en.strings)
        missing_in_fa = set(en.strings) - set(fa.strings)
        assert missing_in_en == set(), f"در en نیست: {missing_in_en}"
        assert missing_in_fa == set(), f"در fa نیست: {missing_in_fa}"

    def test_no_empty_strings(self):
        for catalog in (fa, en):
            empty = [k for k, v in catalog.strings.items() if not v.strip()]
            assert empty == [], f"{catalog.lang} رشته خالی دارد: {empty}"

    def test_placeholders_match(self):
        """پارامترهای هر کلید باید در دو زبان یکی باشد."""
        import re

        for key in fa.strings:
            fa_params = set(re.findall(r"\{(\w+)\}", fa.strings[key]))
            en_params = set(re.findall(r"\{(\w+)\}", en.strings.get(key, "")))
            assert fa_params == en_params, (
                f"کلید {key}: fa={fa_params} ولی en={en_params}"
            )

    def test_persian_uses_half_space(self):
        """نیم‌فاصله درست: 'می‌شود' نه 'میشود'."""
        # فقط کلیدهایی که واقعاً «می» دارند
        for key, text in fa.strings.items():
            if "میشود" in text or "میکند" in text:
                pytest.fail(f"کلید {key} نیم‌فاصله ندارد: {text}")
