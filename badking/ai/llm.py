"""LLM قابل تعویض — هر ارائهدهنده‌ای (OpenAI، Anthropic، مدل محلی، یا هر endpoint سازگار).

طراحی: یک interface ساده + پیادهسازی HTTP سازگار با OpenAI Chat Completions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class LLM(Protocol):
    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> LLMResponse: ...


class OpenAICompatibleLLM:
    """هر endpoint سازگار با OpenAI: OpenAI، LocalAI، Ollama، OpenRouter، …"""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        *,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client
        self.extra_headers = extra_headers or {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> LLMResponse:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "messages": messages, **kwargs}
        client = await self._get_client()
        try:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"خطا در فراخوانی LLM: {e}") from e
        choices = data.get("choices")
        if not choices:
            raise RuntimeError(f"پاسخ LLM فاقد choices است: {str(data)[:200]}")
        message = choices[0].get("message") or {}
        return LLMResponse(
            text=message.get("content") or "",
            tool_calls=message.get("tool_calls") or [],
            raw=data,
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class EchoLLM:
    """LLM ساختگی برای تست و حالت dry-run (بدون هزینه و بدون شبکه)."""

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> LLMResponse:
        last = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        return LLMResponse(text=f"(dry-run) {last.get('content', '') if last else ''}")
