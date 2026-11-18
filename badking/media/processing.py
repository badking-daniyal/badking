"""Voice (STT/TTS) و OCR — wrappers قابلتعویض با هر سرویس.

هیچ وابستگی اجباری ندارند؛ با ارائه callback یا endpoint خارجی کار میکنند.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import httpx


class Voice:
    """تبدیل صوت به متن (STT) و متن به صوت (TTS)."""

    def __init__(
        self,
        stt_url: str | None = None,
        tts_url: str | None = None,
        api_key: str | None = None,
        *,
        stt_func: Callable[[bytes], Awaitable[str]] | None = None,
        tts_func: Callable[[str], Awaitable[bytes]] | None = None,
    ):
        self.stt_url = stt_url
        self.tts_url = tts_url
        self.api_key = api_key
        self.stt_func = stt_func
        self.tts_func = tts_func

    async def to_text(self, audio: bytes, **kwargs: Any) -> str:
        if self.stt_func:
            return await self.stt_func(audio)
        if not self.stt_url:
            raise RuntimeError("STT تنظیم نشده است")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.stt_url, files={"file": ("audio.ogg", audio, "application/octet-stream")},
                headers=self._headers(), data=kwargs,
            )
            data = resp.json()
            return data.get("text", "")

    async def to_speech(self, text: str, **kwargs: Any) -> bytes:
        if self.tts_func:
            return await self.tts_func(text)
        if not self.tts_url:
            raise RuntimeError("TTS تنظیم نشده است")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.tts_url, json={"text": text, **kwargs}, headers=self._headers()
            )
            return resp.content

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}


class OCR:
    """خواندن متن از عکس/سند."""

    def __init__(self, url: str | None = None, api_key: str | None = None,
                 *, func: Callable[[bytes], Awaitable[str]] | None = None):
        self.url = url
        self.api_key = api_key
        self.func = func

    async def read(self, image: bytes, language: str = "fa") -> str:
        if self.func:
            return await self.func(image)
        if not self.url:
            raise RuntimeError("OCR تنظیم نشده است")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.url, files={"file": ("image.png", image, "application/octet-stream")}, data={"language": language},
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
            data = resp.json()
            return data.get("text", "")
