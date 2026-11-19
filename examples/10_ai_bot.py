"""ربات هوش مصنوعی با حافظه گفتگو.

هدف: رباتی که یادش می‌ماند چه گفتید.

    python 10_ai_bot.py

بدون کلید OpenAI هم کار می‌کند: EchoLLM جواب ساده می‌دهد.
برای مدل واقعی، OPENAI_API_KEY را تنظیم کن.
"""

import asyncio
import os

from badking import AIAssistant, Bot, EchoLLM, F, Memory, OpenAICompatibleLLM


def build_llm():
    """اگر کلید داری مدل واقعی، وگرنه پاسخ‌دهنده ساده."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY نیست — از EchoLLM استفاده می‌شود.")
        return EchoLLM()

    return OpenAICompatibleLLM(
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
    )


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"])

    assistant = AIAssistant(
        llm=build_llm(),
        memory=Memory(max_turns=10),  # ده پیام آخر هر کاربر
        system_prompt=(
            "تو یک دستیار فارسی‌زبان هستی. کوتاه و مفید جواب بده. "
            "اگر چیزی را نمی‌دانی، بگو نمی‌دانم."
        ),
    )

    @bot.on_message(F.text == "/start")
    async def start(message):
        await message.reply(
            "سلام! هر چیزی بپرسی جواب می‌دهم.\n"
            "/reset — پاک کردن حافظه گفتگو"
        )

    @bot.on_message(F.text == "/reset")
    async def reset(message):
        assistant.memory.clear(message.from_user.id)
        await message.reply("حافظه پاک شد.")

    @bot.on_message(F.text, ~F.text.startswith("/"))
    async def chat(message):
        # نشانگر «در حال تایپ»
        await bot.send_chat_action(message.chat.id, "typing")

        try:
            answer = await assistant.ask(
                message.from_user.id,
                message.text,
            )
        except Exception as exc:  # noqa: BLE001
            await message.reply(f"خطا در پاسخ: {exc}")
            return

        await message.reply(answer)

    print("ربات هوش مصنوعی روشن شد.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
