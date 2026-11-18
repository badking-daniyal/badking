"""دستیار AI — شخصیت + حافظه + Tool Calling + Intent Router."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from .llm import LLM, LLMResponse
from .memory import Memory


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def run(self, **kwargs: Any) -> Any:
        result = self.func(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result


class IntentRouter:
    """مسیریابی ساده بر اساس کلیدواژه — بدون هزینه LLM."""

    def __init__(self):
        self._routes: list[tuple[list[str], Callable[..., Any]]] = []

    def route(self, keywords: list[str]):
        def deco(fn: Callable[..., Any]):
            self._routes.append((keywords, fn))
            return fn
        return deco

    def match(self, text: str) -> Callable[..., Any] | None:
        low = (text or "").lower()
        for keywords, fn in self._routes:
            if any(k.lower() in low for k in keywords):
                return fn
        return None


class AIAssistant:
    """دستیار کامل: شخصیت + حافظه + ابزارها."""

    def __init__(
        self,
        llm: LLM,
        *,
        persona: str = "تو یک دستیار فارسی‌زبان، مودب و کوتاه‌گو هستی.",
        memory: Memory | None = None,
        tools: list[Tool] | None = None,
        max_tool_rounds: int = 3,
    ):
        self.llm = llm
        self.persona = persona
        self.memory = memory or Memory()
        self.tools = tools or []
        self.max_tool_rounds = max_tool_rounds

    def add_tool(self, name: str, description: str, parameters: dict[str, Any],
                 func: Callable[..., Any]) -> None:
        self.tools.append(Tool(name, description, parameters, func))

    async def reply(self, user_key: str, text: str, **llm_kwargs: Any) -> str:
        self.memory.add(user_key, "user", text)
        messages: list[dict[str, Any]] = [{"role": "system", "content": self.persona}]
        messages.extend(self.memory.history(user_key))

        if self.tools:
            llm_kwargs.setdefault("tools", [t.schema() for t in self.tools])

        response: LLMResponse = await self.llm.chat(messages, **llm_kwargs)

        rounds = 0
        while response.tool_calls and rounds < self.max_tool_rounds:
            rounds += 1
            messages.append({"role": "assistant", "content": response.text or "",
                             "tool_calls": response.tool_calls})
            for call in response.tool_calls:
                fn = call.get("function", {})
                name = fn.get("name")
                args_raw = fn.get("arguments") or "{}"
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except json.JSONDecodeError:
                    args = {}
                tool = next((t for t in self.tools if t.name == name), None)
                if not isinstance(args, dict):
                    args = {}
                try:
                    result = await tool.run(**args) if tool else f"ابزار {name} یافت نشد"
                except Exception as e:
                    # خطای ابزار نباید کل reply را بشکند؛ بهعنوان نتیجه به مدل بده
                    result = f"خطای ابزار {name}: {e}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", name),
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
            response = await self.llm.chat(messages, **llm_kwargs)

        if response.tool_calls and rounds >= self.max_tool_rounds:
            # مدل هنوز ابزار میخواست ولی سقف rounds تمام شد: پاسخ خالی نده
            answer = response.text or "نتوانستم عملیات را کامل کنم (سقف مراحل ابزار)."
        else:
            answer = response.text or ""
        self.memory.add(user_key, "assistant", answer)
        return answer
