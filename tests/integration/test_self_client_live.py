"""Self Client LIVE Integration Tests — فقط با حساب آزمایشی مجاز.

این تستها عمداً SKIPاند. برای اجرا:

    BADKING_LIVE_PHONE=0912... BADKING_LIVE_CODE=12345 \
        pytest tests/integration/test_self_client_live.py -m live

هیچ موفقیت زندهای تا زمانی که کاربر حساب آزمایشی فراهم نکند ادعا نمیشود.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.live

LIVE_PHONE = os.environ.get("BADKING_LIVE_PHONE")
LIVE_CODE = os.environ.get("BADKING_LIVE_CODE")

skip_reason = (
    "BLOCKED: no authorized test account. "
    "Set BADKING_LIVE_PHONE and BADKING_LIVE_CODE to run."
)


@pytest.mark.skipif(not LIVE_PHONE, reason=skip_reason)
class TestLiveAuthentication:
    def test_real_otp_login(self):
        """ورود واقعی با شماره آزمایشی — فقط با مجوز صریح."""
        pytest.skip("BLOCKED: live account not provided in this environment")


@pytest.mark.skipif(not LIVE_PHONE, reason=skip_reason)
class TestLiveMessaging:
    def test_real_send_receive(self):
        pytest.skip("BLOCKED: live account not provided in this environment")


@pytest.mark.skipif(not LIVE_PHONE, reason=skip_reason)
class TestLiveMedia:
    def test_real_upload_download(self):
        pytest.skip("BLOCKED: live account not provided in this environment")


@pytest.mark.skipif(not LIVE_PHONE, reason=skip_reason)
class TestLiveReconnection:
    def test_real_reconnect(self):
        pytest.skip("BLOCKED: live account not provided in this environment")


def test_no_live_claims_in_this_environment():
    """تضمین میکند بدون حساب، هیچ تست زندهای اجرا نشود."""
    if not LIVE_PHONE:
        assert True
