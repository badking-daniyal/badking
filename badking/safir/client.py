"""سرویس سفیر (Safir) — REST جداگانه با Api Access Key.

منبع: docs.bale.ai/safir
قابلیتها: ارسال به شماره، OTP، قالب پیام، پیام رمزدار، دکمهها، request_id (idempotency).
"""

from __future__ import annotations

import secrets
from typing import Any

import httpx

SAFIR_BASE = "https://api.safir.bale.ai"  # پیشفرض؛ قابلتنظیم مطابق مستندات


class SafirClient:
    def __init__(self, api_key: str, *, base_url: str = SAFIR_BASE,
                 timeout: float = 30.0, client: httpx.AsyncClient | None = None):
        if not api_key:
            raise ValueError("Api Access Key لازم است")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client
        self._seen_requests: dict[str, Any] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """ارسال درخواست به سفیر با هدر احراز هویت و idempotency محلی."""
        req_id = payload.get("request_id")
        if req_id and req_id in self._seen_requests:
            return self._seen_requests[req_id]

        client = await self._get_client()
        try:
            resp = await client.post(
                f"{self.base_url}/{endpoint.lstrip('/')}",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            from ..core.errors import NetworkError
            raise NetworkError(f"خطای سفیر در {endpoint}: {e}", method=endpoint) from e

        # فقط پاسخهای موفق کش شوند؛ خطا نباید سمّی شود
        if req_id and data.get("ok") is not False:
            self._seen_requests[req_id] = data
        return data

    async def send_sms(self, phone: str, text: str, *, request_id: str | None = None,
                       buttons: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"phone": phone, "message": text}
        if request_id:
            payload["request_id"] = request_id
        if buttons:
            payload["buttons"] = buttons
        return await self.request("send", payload)

    async def send_template(self, phone: str, template_name: str,
                            variables: dict[str, Any], *, request_id: str | None = None) -> dict[str, Any]:
        """قالب پیام باید از قبل توسط پشتیبانی بله تأیید شده باشد."""
        payload: dict[str, Any] = {
            "phone": phone,
            "template": template_name,
            "variables": variables,
        }
        if request_id:
            payload["request_id"] = request_id
        return await self.request("send-template", payload)

    async def send_encrypted(self, phone: str, text: str, *, request_id: str | None = None) -> dict[str, Any]:
        """پیام رمزدار."""
        payload: dict[str, Any] = {"phone": phone, "message": text}
        if request_id:
            payload["request_id"] = request_id
        return await self.request("send-encrypted", payload)

    def generate_otp(self, length: int = 6) -> str:
        """تولید کد OTP با منبع امن رمزنگاری (ذخیره آن بر عهده برنامه است)."""
        return "".join(str(secrets.randbelow(10)) for _ in range(length))

    async def send_otp(self, phone: str, *, length: int = 6,
                       template_name: str | None = None, request_id: str | None = None) -> tuple[str, dict[str, Any]]:
        """تولید و ارسال OTP. (کد، نتیجه) برمیگرداند."""
        code = self.generate_otp(length)
        if template_name:
            result = await self.send_template(phone, template_name, {"code": code},
                                              request_id=request_id)
        else:
            result = await self.send_sms(phone, f"کد تأیید شما: {code}", request_id=request_id)
        return code, result

    @staticmethod
    def url_button(text: str, url: str) -> dict[str, Any]:
        return {"type": "url", "text": text, "url": url}

    @staticmethod
    def web_app_button(text: str, url: str) -> dict[str, Any]:
        return {"type": "web_app", "text": text, "url": url}

    @staticmethod
    def copy_button(text: str, copy_text: str) -> dict[str, Any]:
        return {"type": "copy_text", "text": text, "copy_text": copy_text}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
