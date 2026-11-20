"""تست OTP Security — محدودیت تلاش، انقضا، جلوگیری از استفاده مجدد."""

from __future__ import annotations

import pytest

from badking.hybrid.security import (
    OTPAlreadyUsed,
    OTPAttemptLimitExceeded,
    OTPExpired,
    OTPGuard,
)


class TestOTPGuard:
    def test_correct_code(self):
        g = OTPGuard()
        g.issue("c1", "1234", now=0)
        assert g.verify("c1", "1234", now=1) is True

    def test_wrong_code(self):
        g = OTPGuard()
        g.issue("c1", "1234", now=0)
        assert g.verify("c1", "9999", now=1) is False

    def test_reuse_blocked(self):
        g = OTPGuard()
        g.issue("c1", "1234", now=0)
        assert g.verify("c1", "1234", now=1) is True
        with pytest.raises(OTPAlreadyUsed):
            g.verify("c1", "1234", now=2)

    def test_expiry(self):
        g = OTPGuard(ttl_seconds=60)
        g.issue("c1", "1234", now=0)
        with pytest.raises(OTPExpired):
            g.verify("c1", "1234", now=61)

    def test_attempt_limit(self):
        g = OTPGuard(max_attempts=3)
        g.issue("c1", "1234", now=0)
        for t in (1, 2, 3):
            assert g.verify("c1", "9999", now=t) is False
        with pytest.raises(OTPAttemptLimitExceeded):
            g.verify("c1", "1234", now=4)

    def test_unknown_challenge(self):
        g = OTPGuard()
        assert g.verify("none", "1234", now=0) is False

    def test_code_not_stored_in_plaintext(self):
        g = OTPGuard()
        g.issue("c1", "1234", now=0)
        ch = g._challenges["c1"]
        assert "1234" not in ch.code_hash
        assert len(ch.code_hash) == 64

    def test_clear(self):
        g = OTPGuard()
        g.issue("c1", "1234", now=0)
        g.clear("c1")
        assert g.verify("c1", "1234", now=1) is False
