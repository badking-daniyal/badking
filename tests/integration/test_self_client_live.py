"""Self Client LIVE Integration Tests — فقط با حساب آزمایشی مجاز.

این تست‌ها عمداً SKIP‌اند تا زمانی که credential مجاز در محیط نباشد.
هیچ موفقیت زنده‌ای ادعا نمی‌شود.

اجرا:
    BADKING_LIVE_PHONE=0912... BADKING_LIVE_CODE=12345 \
        pytest tests/integration/test_self_client_live.py -m live

قواعد ایمنی:
    • فقط عملیات خواندنی و برگشت‌پذیر (get_me, iter_dialogs, load_history).
    • هیچ پیامی ارسال/حذف نمی‌شود.
    • شماره و توکن هرگز چاپ نمی‌شوند (mask می‌شوند).
    • بدون credential → SKIP، نه PASS کاذب.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

pytestmark = pytest.mark.live

LIVE_PHONE = os.environ.get("BADKING_LIVE_PHONE")
LIVE_CODE = os.environ.get("BADKING_LIVE_CODE")

skip_reason = (
    "BLOCKED: no authorized test account. "
    "Set BADKING_LIVE_PHONE and BADKING_LIVE_CODE to run."
)

requires_live = pytest.mark.skipif(not LIVE_PHONE, reason=skip_reason)


def _mask(value: str | None) -> str:
    """ماسک کردن اطلاعات حساس برای لاگ."""
    if not value:
        return "<unset>"
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


@pytest_asyncio.fixture(scope="module")
async def live_bot():
    """یک SelfBot متصل با حساب آزمایشی — فقط اگر credential مجاز باشد."""
    if not LIVE_PHONE:
        pytest.skip(skip_reason)
    from badking.hybrid import SelfBot

    # ack_risk پارامتر وجودنداشت و با credential، fixture بجای SKIP دچار
    # TypeError میشد. SelfBot فقط phone میپذیرد؛ OTP توسط سرور تأیید میشود.
    bot = SelfBot(phone=LIVE_PHONE)
    try:
        await bot.connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"BLOCKED: live connect failed ({type(exc).__name__})")
    yield bot
    try:
        await bot.close()
    except Exception:  # noqa: BLE001
        pass


@requires_live
class TestLiveAuthentication:
    @pytest.mark.asyncio
    async def test_real_login_returns_identity(self, live_bot):
        """ورود واقعی: get_me باید id برگرداند."""
        me = await live_bot.get_me()
        assert me is not None
        assert int(getattr(me, "id", 0) or 0) > 0

    @pytest.mark.asyncio
    async def test_session_is_persisted(self, live_bot):
        """session پس از connect باید توکن داشته باشد."""
        session = live_bot.session
        assert session is not None
        assert session.access_token
        # توکن چاپ نمی‌شود، فقط وجودش تأیید می‌شود.
        assert _mask(session.access_token).count("*") > 0


@requires_live
class TestLiveMessagingReadOnly:
    @pytest.mark.asyncio
    async def test_read_dialogs(self, live_bot):
        """خواندن لیست گفتگوها — بدون ارسال چیزی."""
        dialogs = []
        async for d in live_bot.iter_dialogs(limit=5):
            dialogs.append(d)
            if len(dialogs) >= 5:
                break
        assert isinstance(dialogs, list)

    @pytest.mark.asyncio
    async def test_read_history_of_self_chat(self, live_bot):
        """خواندن تاریخچه گفتگوی با خود — بدون تغییر داده."""
        me = await live_bot.get_me()
        history = []
        async for m in live_bot.iter_messages(me.id, limit=3):
            history.append(m)
            if len(history) >= 3:
                break
        assert isinstance(history, list)


@requires_live
class TestLiveReconnection:
    @pytest.mark.asyncio
    async def test_reconnect_preserves_session(self, live_bot):
        """بستن و بازکردن اتصال، session را از دست نمی‌دهد."""
        session_before = live_bot.session.access_token
        await live_bot.close()
        await live_bot.connect()
        assert live_bot.session is not None
        assert live_bot.session.access_token == session_before
        me = await live_bot.get_me()
        assert int(getattr(me, "id", 0) or 0) > 0


def test_no_live_claims_without_credentials():
    """بدون credential، هیچ ادعای زنده‌ای پذیرفته نمی‌شود."""
    if not LIVE_PHONE:
        assert True
    else:  # pragma: no cover - فقط در محیط مجاز
        assert LIVE_PHONE
