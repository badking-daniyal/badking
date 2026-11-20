"""Access Control Audit — تضمین deny-by-default در تمام مسیرهای حساس.

هیچ مسیر حساسی نباید بدون مجوز اجرا شود. تستها صریحاً بررسی میکنند که
با PermissionPolicy() (خالی) تمام متدهای حساس PermissionDenied بدهند.
"""

from __future__ import annotations

import asyncio

import pytest

from badking.hybrid import SelfBot
from badking.hybrid.security import (
    ALL_PERMISSIONS,
    DANGEROUS_RPCS,
    PermissionDenied,
    PermissionPolicy,
)
from badking.hybrid.session import Session


def make_denied_bot():
    """بات با policy خالی — تمام مجوزها رد میشوند."""
    bot = SelfBot(
        session=Session(access_token="x", user_id=1),
        permissions=PermissionPolicy(),
    )
    bot._transport = object()  # pretend connected
    return bot


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestDenyByDefault:
    def test_default_policy_is_empty(self):
        bot = SelfBot(session=Session(access_token="x", user_id=1))
        assert bot.permissions.allow == frozenset()
        assert bot.legacy_unrestricted is False

    def test_call_denied(self):
        bot = make_denied_bot()
        with pytest.raises(PermissionDenied):
            run(bot.call("messaging.SendMessage", peer={}, message_id=1, content={}, chat={}))

    def test_raw_call_denied(self):
        bot = make_denied_bot()
        with pytest.raises(PermissionDenied):
            run(bot.raw_call("messaging.SendMessage", {}))

    def test_all_dangerous_rpcs_denied(self):
        policy = PermissionPolicy()
        for rpc in DANGEROUS_RPCS:
            with pytest.raises(PermissionDenied):
                policy.check(rpc)

    def test_no_permission_equals_deny_all(self):
        """نبود مجوز نباید به معنای دسترسی نامحدود باشد."""
        policy = PermissionPolicy()
        for permission in ALL_PERMISSIONS:
            assert not policy.has(permission)


class TestLegacyOptIn:
    def test_legacy_requires_explicit_flag(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            bot = SelfBot(
                session=Session(access_token="x", user_id=1),
                legacy_unrestricted=True,
            )
        assert bot.permissions is None
        assert bot.legacy_unrestricted is True
        assert len(caught) >= 1
        assert "Production" in str(caught[0].message)

    def test_legacy_not_silently_enabled(self):
        """نباید بدون پرچم صریح، حالت legacy فعال شود."""
        bot = SelfBot(session=Session(access_token="x", user_id=1))
        assert bot.legacy_unrestricted is False


class TestAllSensitivePathsCovered:
    """تضمین میکند متدهای حساس از self.call میگذرند (که چک مجوز دارد)."""

    def test_no_direct_transport_request_outside_call_and_raw_call(self):
        import inspect
        from badking.hybrid import client as client_mod

        src = inspect.getsource(client_mod.SelfBot)
        # دو مسیر مستقیم مجازاند: call و raw_call (هر دو چک مجوز دارند)
        assert src.count("self._transport.request") == 2

    def test_permission_check_present_in_both_paths(self):
        import inspect
        from badking.hybrid import client as client_mod

        src = inspect.getsource(client_mod.SelfBot)
        assert src.count("self.permissions.check(full_name)") == 2
