"""Connector عمومی — ارسال هر چیزی به هر جا.

هر URL، هر متد HTTP، هر نوع auth (Bearer/Basic/ApiKey)، retry با backoff، و لاگ.
این همان چیزی است که «ربات متصل به دنیای بیرون» را ممکن میکند:
زرینپال، گوگل شیت، CRM، دیتابیس، یا هر سرویس دیگری.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

logger = logging.getLogger("badking.connector")


@dataclass
class Auth:
    """احراز هویت قابلتنظیم."""

    type: str = "none"  # none | bearer | basic | apikey
    token: str | None = None
    username: str | None = None
    password: str | None = None
    header_name: str = "X-API-Key"
    header_value: str | None = None

    def headers(self) -> dict[str, str]:
        if self.type == "bearer" and self.token:
            return {"Authorization": f"Bearer {self.token}"}
        if self.type == "basic" and self.username and self.password:
            import base64
            cred = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            return {"Authorization": f"Basic {cred}"}
        if self.type == "apikey" and self.header_value:
            return {self.header_name: self.header_value}
        return {}


@dataclass
class ConnectorResult:
    status_code: int
    data: Any
    headers: dict[str, str] = field(default_factory=dict)
    attempts: int = 1


class Connector:
    """کلاینت HTTP عمومی با retry و لاگ."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        auth: Auth | None = None,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 0.5,
        default_headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        on_log: Callable[[str], None] | None = None,
    ):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.auth = auth or Auth()
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.default_headers = default_headers or {}
        self._client = client
        self.on_log = on_log

    def _log(self, msg: str) -> None:
        logger.info(msg)
        if self.on_log:
            self.on_log(msg)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if self.base_url:
            return f"{self.base_url}/{path.lstrip('/')}"
        raise ValueError("base_url تنظیم نشده یا URL کامل داده نشده است")

    async def request(
        self,
        method: str,
        path: str = "",
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        data: Any = None,
        content: str | bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> ConnectorResult:
        url = self._url(path)
        all_headers = {**self.default_headers, **self.auth.headers(), **(headers or {})}
        client = await self._get_client()
        last_exc: Exception | None = None

        total = max(1, self.retries)  # retries=0 نباید به معنای «صفر تلاش» باشد
        for attempt in range(1, total + 1):
            self._log(f"{method} {url} (attempt {attempt})")
            try:
                resp = await client.request(
                    method.upper(), url, params=params, json=json_body,
                    data=data, content=content, headers=all_headers,
                )
                # 429 (rate limit) و 5xx قابل retryاند
                retryable = resp.status_code == 429 or resp.status_code >= 500
                if retryable and attempt < total:
                    delay = self.backoff * (2 ** (attempt - 1))
                    if resp.status_code == 429:
                        try:
                            delay = max(delay, float(resp.headers.get("Retry-After", 0)))
                        except (TypeError, ValueError):
                            pass
                    await asyncio.sleep(delay)
                    continue
                try:
                    parsed = resp.json()
                except Exception:
                    parsed = resp.text
                return ConnectorResult(resp.status_code, parsed, dict(resp.headers), attempt)
            except httpx.HTTPError as e:
                last_exc = e
                if attempt < total:
                    await asyncio.sleep(self.backoff * (2 ** (attempt - 1)))
        raise httpx.HTTPError(f"شکست بعد از {total} تلاش: {last_exc}") from last_exc

    # متدهای راحت
    async def get(self, path: str = "", **kwargs: Any) -> ConnectorResult:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str = "", **kwargs: Any) -> ConnectorResult:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str = "", **kwargs: Any) -> ConnectorResult:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str = "", **kwargs: Any) -> ConnectorResult:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str = "", **kwargs: Any) -> ConnectorResult:
        return await self.request("DELETE", path, **kwargs)

    async def send_webhook(self, url: str, payload: Any, *, secret: str | None = None) -> ConnectorResult:
        """ارسال webhook به هر سرویس، با امضای HMAC اختیاری."""
        headers = {}
        if secret:
            import hashlib
            import hmac
            import json
            body = json.dumps(payload, ensure_ascii=False)
            sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-Badking-Signature"] = sig
            return await self.request("POST", url, content=body,
                                      headers={"Content-Type": "application/json", **headers})
        return await self.post(url, json_body=payload, headers=headers)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
