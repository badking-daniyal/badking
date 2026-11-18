"""تستهای فاز ۴: حافظه، LLM، Tool Calling، Intent Router، RAG."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking.ai import (  # noqa: E402
    AIAssistant, EchoLLM, IntentRouter, LLMResponse, Memory, OpenAICompatibleLLM, SimpleRAG, Tool,
)


def test_memory():
    m = Memory()
    m.add("u1", "user", "سلام")
    m.add("u1", "assistant", "درود")
    m.set_fact("u1", "name", "علی")
    assert len(m.history("u1")) == 2
    assert m.get_fact("u1", "name") == "علی"
    m.clear("u1")
    assert m.history("u1") == []


@pytest.mark.asyncio
async def test_echo_llm():
    llm = EchoLLM()
    r = await llm.chat([{"role": "user", "content": "تست"}])
    assert "تست" in r.text


@pytest.mark.asyncio
async def test_assistant_with_tool():
    class ScriptedLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(text="", tool_calls=[{
                    "id": "call1", "type": "function",
                    "function": {"name": "weather", "arguments": '{"city": "تهران"}'},
                }])
            # در نوبت دوم، آخرین پیام tool را بررسی میکند
            tool_result = next((m for m in messages if m.get("role") == "tool"), None)
            assert tool_result is not None
            assert "آفتابی" in tool_result["content"]
            return LLMResponse(text="هوای تهران آفتابی است.")

    llm = ScriptedLLM()
    assistant = AIAssistant(llm, memory=Memory())
    assistant.add_tool("weather", "آب و هوا",
                       {"type": "object", "properties": {"city": {"type": "string"}}},
                       lambda city: f"{city}: آفتابی")
    reply = await assistant.reply("u1", "هوا چطوره؟")
    assert "آفتابی" in reply
    assert llm.calls == 2


def test_intent_router():
    router = IntentRouter()

    @router.route(["خرید", "سفارش"])
    def buy(text):
        return "buy"

    assert router.match("میخوام خرید کنم") is buy
    assert router.match("سلام") is None


def test_rag_persian_normalization():
    rag = SimpleRAG(chunk_size=100)
    rag.add_text("کتابخانه بله یک فریمورک قدرتمند است. سفیر برای ارسال پیام است.", "doc1")
    results = rag.search("سفیر پیام")
    assert results
    assert "سفیر" in results[0].text
