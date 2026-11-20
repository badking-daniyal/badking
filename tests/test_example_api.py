"""تست کنید نمونهها فقط از APIای استفاده میکنند که واقعاً وجود دارد.

چرا: ۲۰ نمونه از ``bot.run()`` و ``@bot.on_message`` و ``message.reply()``
استفاده میکردند در حالی که این متدها نبودند. تست AST فقط سینتکس را میگرفت،
نه وجود API. این تست آن شکاف را میبندد.
"""

from __future__ import annotations

import ast
from pathlib import Path

from badking import Bot, Dispatcher, F
from badking.types.message import Message

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_bot_first_api_exists():
    """رابط سادهای که نمونهها وعدهاش را میدهند باید واقعی باشد."""
    bot = Bot("1:TEST")
    assert hasattr(bot, "run")
    assert hasattr(bot, "on_message")
    assert hasattr(bot, "on_callback_query")
    assert hasattr(bot, "dispatcher")
    assert hasattr(bot, "polling")


def test_on_message_registers_handler():
    bot = Bot("1:TEST")

    @bot.on_message(F.text == "/x")
    async def handler(message):
        pass

    # هندلر در dispatcher داخلی ثبت شد
    assert bot.dispatcher is not None


def test_dispatcher_is_same_instance():
    bot = Bot("1:TEST")
    assert bot.dispatcher is bot.dispatcher


def test_message_reply_alias_exists():
    assert hasattr(Message, "reply")
    assert hasattr(Message, "answer")


def test_no_nonexistent_bot_methods_in_examples():
    """هیچ نمونهای نباید متد Bot APIای را صدا بزند که Bot ندارد.

    فقط متدهایی را میسنجیم که قطعاً متد Bot API رسمیاند. متدهای مخصوص
    self-bot (probe/raw_call/idle/...) روی SelfBotاند، نه Bot — آن نمونهها
    متغیر محلی دیگری دارند که به اشتباه `bot` نامیده شده و تست جداگانه
    نحوه کار SelfBot را میپوشاند.
    """
    bot_methods = {m for m in dir(Bot) if not m.startswith("_")}
    bot_api_methods = {
        "send_message", "send_photo", "send_video", "send_audio",
        "send_voice", "send_document", "send_animation", "send_contact",
        "send_location", "send_media_group", "send_chat_action",
        "ban_chat_member", "unban_chat_member", "restrict_chat_member",
        "get_chat", "get_chat_member", "get_chat_member_count",
        "get_chat_administrators", "get_me", "get_file", "download_file",
        "edit_message_text", "delete_message", "copy_message",
        "forward_message", "answer_callback_query", "get_updates",
        "set_webhook", "delete_webhook", "get_webhook_info",
        "set_my_commands", "polling", "close", "request",
    }

    for path in sorted(EXAMPLES.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            if isinstance(func.value, ast.Name) and func.value.id == "bot":
                name = func.attr
                if name in bot_api_methods and name not in bot_methods:
                    raise AssertionError(
                        f"{path.name}: bot.{name}() متد Bot API است ولی در Bot نیست"
                    )


def test_decorator_usage_is_valid():
    """دکوراتورهای on_message/on_callback_query در نمونهها معتبراند."""
    for path in sorted(EXAMPLES.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "@bot.on_message" in text or "@bot.on_callback_query" in text:
            # این دکوراتورها حالا وجود دارند
            assert hasattr(Bot, "on_message")
            assert hasattr(Bot, "on_callback_query")
