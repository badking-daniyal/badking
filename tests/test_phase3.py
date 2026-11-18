"""تستهای فاز ۳: MiniApp HMAC، سفیر، پرداخت، Business API."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking.business import BusinessBot  # noqa: E402
from badking.miniapp import InvalidInitData, generate_test_init_data, validate_init_data  # noqa: E402
from badking.payments import PaymentToolkit  # noqa: E402
from badking.safir import SafirClient  # noqa: E402


TOKEN = "123456:TESTTOKEN"


def test_miniapp_valid():
    raw = generate_test_init_data(TOKEN, user_id=42, first_name="علی")
    data = validate_init_data(raw, TOKEN)
    assert data.user.id == 42
    assert data.user.first_name == "علی"
    assert data.is_fresh


def test_miniapp_invalid_signature():
    raw = generate_test_init_data(TOKEN)
    with pytest.raises(InvalidInitData):
        validate_init_data(raw, "999:WRONGTOKEN")


def test_miniapp_tampered():
    raw = generate_test_init_data(TOKEN) + "&user=%7B%22id%22%3A999%7D"
    with pytest.raises(InvalidInitData):
        validate_init_data(raw, TOKEN)


@pytest.mark.asyncio
async def test_safir_idempotency():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"ok": True, "message_id": "m1"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    safir = SafirClient("KEY", client=client)
    r1 = await safir.send_sms("09123456789", "سلام", request_id="req-1")
    r2 = await safir.send_sms("09123456789", "سلام", request_id="req-1")
    assert r1 == r2
    assert len(calls) == 1  # دومی ارسال نشد (idempotency)
    await safir.close()


def test_safir_otp_and_buttons():
    safir = SafirClient("KEY")
    code = safir.generate_otp(6)
    assert code.isdigit() and len(code) == 6
    btn = SafirClient.copy_button("کپی کد", code)
    assert btn["type"] == "copy_text"


@pytest.mark.asyncio
async def test_payment_invoice():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"ok": True, "result": {
            "message_id": 1, "date": 1,
            "chat": {"id": 123, "type": "private"},
            "text": "faktura",
        }})

    bot = __import__("badking").Bot(TOKEN, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    pay = PaymentToolkit(bot)
    msg = await pay.send_invoice(123, "محصول", "توضیحات", "payload-1", "IRR",
                                 [{"label": "قیمت", "amount": 1000}])
    assert msg.message_id == 1
    assert "sendInvoice" in calls[0]
    await bot.close()


def test_business_base_url():
    bot = BusinessBot(TOKEN)
    assert "/business/bot" in bot.api_url
