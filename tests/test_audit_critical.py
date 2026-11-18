"""تستهای قراردادی برای رفع باگهای بحرانی ممیزی.

وکتور HMAC بهصورت مستقل (با الگوریتم مستندات بله) محاسبه شده،
نه توسط generate_test_init_data کتابخانه — تا تست self-compatible نباشد.
"""

from __future__ import annotations

import hashlib
import hmac
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking.miniapp.init_data import (  # noqa: E402
    InvalidInitData,
    generate_test_init_data,
    validate_init_data,
)
from badking.safir.client import SafirClient  # noqa: E402


# ---------- HMAC مینیاپ ----------
def _official_init_data(token: str, auth_date: int) -> str:
    """ساخت initData دقیقاً طبق مستندات رسمی بله (الفبایی + \\n)."""
    data = {
        "auth_date": str(auth_date),
        "query_id": "AAHd",
        "user": '{"id":123,"first_name":"تستر"}',
    }
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_validate_official_style_init_data():
    token = "123456:TESTTOKEN"
    raw = _official_init_data(token, int(time.time()))
    parsed = validate_init_data(raw, token)
    assert parsed.user.id == 123
    assert parsed.query_id == "AAHd"


def test_generate_then_validate_roundtrip():
    token = "123456:TESTTOKEN"
    raw = generate_test_init_data(token)
    parsed = validate_init_data(raw, token)
    assert parsed.user.id == 123


def test_reject_bad_signature():
    raw = _official_init_data("tokenA", int(time.time()))
    with pytest.raises(InvalidInitData):
        validate_init_data(raw, "tokenB")


def test_reject_missing_auth_date():
    token = "123456:TESTTOKEN"
    data = {"query_id": "AAHd", "user": '{"id":1,"first_name":"x"}'}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    with pytest.raises(InvalidInitData):
        validate_init_data(urlencode(data), token)


def test_reject_expired_and_future():
    token = "123456:TESTTOKEN"
    with pytest.raises(InvalidInitData):
        validate_init_data(_official_init_data(token, int(time.time()) - 100000), token, max_age=60)
    with pytest.raises(InvalidInitData):
        validate_init_data(_official_init_data(token, int(time.time()) + 100000), token, max_age=60)


def test_is_fresh_rejects_future():
    from badking.miniapp.init_data import WebAppInitData
    obj = WebAppInitData(query_id=None, user=None, auth_date=int(time.time()) + 100000, raw={})
    assert obj.is_fresh() is False


# ---------- OTP امن ----------
def test_otp_uses_secure_random(monkeypatch):
    client = SafirClient("key")
    code = client.generate_otp(6)
    assert len(code) == 6
    assert code.isdigit()
    # مطمئن شویم secrets.randbelow فراخوانی میشود، نه random.randint
    import badking.safir.client as mod
    assert mod.random is None if hasattr(mod, "random") else True
    assert hasattr(mod, "secrets")


# ---------- idempotency سفیر ----------
def test_safir_does_not_cache_errors():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(200, json={"ok": False, "error": "transient"})
        return httpx.Response(200, json={"ok": True, "result": "sent"})

    client = SafirClient("key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    import asyncio
    async def scenario():
        r1 = await client.send_sms("123", "salam", request_id="rid1")
        r2 = await client.send_sms("123", "salam", request_id="rid1")
        assert r1["ok"] is False
        assert r2["ok"] is True
        assert len(calls) == 2
        await client.close()
    asyncio.run(scenario())


def test_safir_caches_success():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"ok": True, "result": "sent"})

    client = SafirClient("key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    import asyncio
    async def scenario():
        await client.send_sms("123", "salam", request_id="rid2")
        await client.send_sms("123", "salam", request_id="rid2")
        assert len(calls) == 1
        await client.close()
    asyncio.run(scenario())


def test_safir_raises_on_http_error():
    def handler(request):
        return httpx.Response(500, json={"error": "server"})
    client = SafirClient("key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    import asyncio
    from badking.core.errors import NetworkError
    async def scenario():
        with pytest.raises(NetworkError):
            await client.send_sms("123", "salam")
        await client.close()
    asyncio.run(scenario())
