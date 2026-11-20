"""تست integration: OTPGuard واقعاً در AuthFlow استفاده میشود."""

from __future__ import annotations

import pytest

from badking.hybrid.auth import AuthError, AuthFlow
from badking.hybrid.proto import build
from badking.hybrid.security import OTPGuard


class _OKTransport:
    """سرور فرضی که همیشه ورود موفق برمیگرداند."""

    def __init__(self):
        self.calls = 0

    async def request(self, payload):
        self.calls += 1
        return build({4: "token", 6: 1})


class _RejectingTransport:
    """سرور فرضی که کد اشتباه را رد میکند (خطای 400)."""

    def __init__(self):
        self.calls = 0

    async def request(self, payload):
        self.calls += 1
        return build({15: 400, 16: "کد نادرست"})


def _flow(guard, transport=None):
    return AuthFlow(transport or _OKTransport(), otp_guard=guard)


@pytest.mark.asyncio
async def test_otp_guard_wired_brute_force_blocked():
    """کد اشتباه مکرر پس از max_attempts حتی قبل از سرور رد میشود."""
    guard = OTPGuard(max_attempts=2, ttl_seconds=100)
    transport = _RejectingTransport()  # سرور کدها را رد میکند
    flow = _flow(guard, transport)
    # حالت blind: هر تلاش شمارش میشود، صحت کد توسط سرور تعیین میشود.
    for code in ("1111", "2222"):
        with pytest.raises(AuthError, match="کد نادرست"):
            await flow.sign_in("tx", code)
    with pytest.raises(AuthError, match="بیش از حد"):
        await flow.sign_in("tx", "3333")  # تلاش ۳ → رد قبل از سرور
    assert transport.calls == 2  # سومین به سرور نرسید


@pytest.mark.asyncio
async def test_otp_guard_replay_blocked():
    """همان کد دوباره روی همان transaction رد میشود."""
    guard = OTPGuard(max_attempts=5, ttl_seconds=100)
    transport = _OKTransport()
    flow = _flow(guard, transport)
    await flow.sign_in("tx", "1234")
    with pytest.raises(AuthError, match="قبلاً استفاده"):
        await flow.sign_in("tx", "1234")
    assert transport.calls == 1  # دومین به سرور نرسید


@pytest.mark.asyncio
async def test_otp_guard_expiry_blocked():
    """کد منقضی رد میشود."""
    guard = OTPGuard(max_attempts=5, ttl_seconds=1)
    transport = _OKTransport()
    flow = _flow(guard, transport)
    # چالش را با timestamp قدیمی صادر میکنیم
    import time

    guard.issue_blind("tx", now=time.time() - 10)
    with pytest.raises(AuthError, match="منقضی"):
        await flow.sign_in("tx", "1234")
    assert transport.calls == 0


@pytest.mark.asyncio
async def test_otp_guard_reset_after_success():
    """transaction تازه چالش مستقل میگیرد؛ قبلی مصرفشده باقی میماند."""
    guard = OTPGuard(max_attempts=5, ttl_seconds=100)
    flow = _flow(guard)
    await flow.sign_in("tx1", "1234")
    # چالش قبلی مصرفشده مانده تا replay جلوگیری شود
    assert guard._challenges["tx1"].used is True
    # transaction تازه مستقل است و مشکلی ندارد
    await flow.sign_in("tx2", "1234")
    assert guard._challenges["tx2"].used is True


@pytest.mark.asyncio
async def test_otp_guard_rejects_invalid_format_before_server():
    """کد نامعتبر حتی با guard هم قبل از سرور رد میشود."""
    guard = OTPGuard()
    transport = _OKTransport()
    flow = _flow(guard, transport)
    with pytest.raises(AuthError):
        await flow.sign_in("tx", "abc")
    assert transport.calls == 0


@pytest.mark.asyncio
async def test_otp_guard_disabled_keeps_legacy_behavior():
    """Regression: بدون guard رفتار قدیمی تغییر نکرده است."""
    transport = _OKTransport()
    flow = AuthFlow(transport)  # بدون otp_guard
    await flow.sign_in("tx", "1234")
    await flow.sign_in("tx", "1234")  # replay مجاز در حالت قدیمی
    assert transport.calls == 2
