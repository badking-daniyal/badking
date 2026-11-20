"""تست قابلیتهای امنیتی Self Client — هر ادعا با تست پوشش داده میشود."""

from __future__ import annotations

import asyncio
import logging

import pytest

from badking.hybrid.security import (
    ALL_PERMISSIONS,
    DANGEROUS_RPCS,
    PermissionDenied,
    PermissionPolicy,
    SessionExpiry,
    auth_error_hint,
    constant_time_equals,
    mask_hash,
    mask_phone,
    mask_token,
    secure_log_context,
    validate_otp,
)


class TestOTPValidation:
    @pytest.mark.parametrize("code,expected", [
        ("1234", "1234"),
        (" 1234 ", "1234"),
        ("12-34", "1234"),
        ("1 2 3 4", "1234"),
        ("12345678", "12345678"),
    ])
    def test_valid(self, code, expected):
        assert validate_otp(code) == expected

    @pytest.mark.parametrize("code", ["", "   ", "abc", "123", "123456789", "12a4", None, 1234])
    def test_invalid(self, code):
        with pytest.raises(ValueError):
            validate_otp(code)


class TestSecureLogging:
    def test_phone_masked(self):
        assert mask_phone("989123456789") == "********6789"
        assert "912345" not in mask_phone("989123456789")

    def test_token_masked(self):
        masked = mask_token("123456:SECRETVALUE")
        assert "SECRETVALUE" not in masked
        assert masked.endswith("VALUE") is False or len(masked) < 10

    def test_hash_fingerprint(self):
        fp = mask_hash("my-transaction-hash")
        assert "my-transaction" not in fp
        assert fp.startswith("sha256:")

    def test_context_masks_all_sensitive_keys(self):
        ctx = secure_log_context(
            phone="989123456789",
            access_token="abc:secret123",
            transaction_hash="tx-abcdef",
            code="1234",
            normal="hello",
        )
        assert "989123" not in ctx["phone"]
        assert "secret123" not in ctx["access_token"]
        assert "tx-abcdef" not in ctx["transaction_hash"]
        assert ctx["code"] == "***"
        assert ctx["normal"] == "hello"

    def test_auth_logger_does_not_log_full_phone(self, caplog):
        """لاگر auth نباید شماره کامل را چاپ کند."""
        from badking.hybrid.auth import AuthFlow, AuthError

        class FakeTransport:
            async def request(self, payload):
                raise AuthError("test")

        flow = AuthFlow(FakeTransport())
        with caplog.at_level(logging.INFO, logger="badking.hybrid.auth"):
            try:
                asyncio.get_event_loop().run_until_complete(
                    flow.request_code("09123456789")
                )
            except AuthError:
                pass
        assert "09123456789" not in caplog.text
        assert "989123456789" not in caplog.text


class TestRBAC:
    def test_default_denies_everything(self):
        policy = PermissionPolicy()
        assert policy.allow == frozenset()
        with pytest.raises(PermissionDenied):
            policy.check("messaging.SendMessage")

    def test_explicit_permission_allows(self):
        policy = PermissionPolicy(allow=frozenset({"send_messages"}))
        policy.check("messaging.SendMessage")  # no exception

    def test_dangerous_blocked_even_with_related_permission(self):
        policy = PermissionPolicy(allow=frozenset({"delete_messages"}))
        with pytest.raises(PermissionDenied) as exc:
            policy.check("messaging.DeleteMessage")
        assert exc.value.required == "dangerous"

    def test_dangerous_allowed_explicitly(self):
        policy = PermissionPolicy(
            allow=frozenset({"delete_messages"}), allow_dangerous=True
        )
        policy.check("messaging.DeleteMessage")

    def test_full_policy(self):
        policy = PermissionPolicy.full()
        for rpc in DANGEROUS_RPCS:
            policy.check(rpc)

    def test_unknown_permission_rejected(self):
        with pytest.raises(ValueError):
            PermissionPolicy(allow=frozenset({"superuser"}))

    def test_client_enforces_rbac(self):
        from badking.hybrid import SelfBot
        from badking.hybrid.session import Session

        bot = SelfBot(
            session=Session(access_token="x", user_id=1),
            permissions=PermissionPolicy(allow=frozenset({"read_messages"})),
        )
        bot._transport = object()  # pretend connected

        async def attempt():
            await bot.call("messaging.SendMessage", peer={}, message_id=1, content={}, chat={})

        with pytest.raises(PermissionDenied):
            asyncio.get_event_loop().run_until_complete(attempt())

    def test_client_without_policy_unchanged(self):
        """سازگاری: بدون policy رفتار قبل حفظ میشود."""
        from badking.hybrid import SelfBot
        from badking.hybrid.session import Session

        bot = SelfBot(session=Session(access_token="x", user_id=1))
        assert bot.permissions is None


class TestSessionExpiry:
    def test_fresh(self):
        exp = SessionExpiry(max_age_seconds=100)
        now = 1000.0
        assert not exp.is_expired(touched_at=now, now=now)

    def test_expired(self):
        exp = SessionExpiry(max_age_seconds=100)
        assert exp.is_expired(touched_at=0, now=200)

    def test_never_touched(self):
        exp = SessionExpiry()
        assert exp.is_expired(touched_at=None)

    def test_absolute_limit(self):
        exp = SessionExpiry(max_age_seconds=100000, absolute_seconds=50)
        exp._created = 0.0  # deterministic: created 50+ seconds ago
        assert exp.is_expired(touched_at=49, now=100)

    def test_remaining(self):
        exp = SessionExpiry(max_age_seconds=100)
        assert exp.remaining(touched_at=40, now=50) == 90
        assert exp.remaining(touched_at=0, now=500) == 0


class TestMisc:
    def test_auth_error_hint(self):
        assert "429" not in auth_error_hint(429)
        assert auth_error_hint(429)

    def test_constant_time_equals(self):
        assert constant_time_equals("abc", "abc")
        assert not constant_time_equals("abc", "abd")
