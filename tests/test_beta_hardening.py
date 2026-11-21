"""Beta hardening regression tests — Independent audit findings (2026-11-20).

Each test reproduces a CONCRETE defect found by direct source review and
asserts the fix. No existing test is weakened or deleted.
"""

from __future__ import annotations

import asyncio
import io
import logging

import pytest

from badking.hybrid.client import SelfBot
from badking.hybrid.download import (
    DEFAULT_MAX_SIZE,
    sanitize_filename,
    validate_download_url,
)
from badking.hybrid.schema import METHODS
from badking.hybrid.security import (
    DANGEROUS_RPCS,
    PermissionDenied,
    PermissionPolicy,
)
from badking.hybrid.session import Session


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def denied_bot():
    bot = SelfBot(
        session=Session(access_token="x", user_id=1),
        permissions=PermissionPolicy(),
    )
    bot._transport = object()
    return bot


# ---------- Client API correctness ----------

def test_get_pinned_reads_data_key():
    """LoadPinnedMessages response field 1 is `data`, not `pins_data`."""
    from badking.hybrid.schema import RESPONSES

    assert "data" in RESPONSES["LoadPinnedMessages"]
    assert "pins_data" in RESPONSES["GetPins"]  # old key belonged to GetPins

    bot = SelfBot(session=Session(access_token="x", user_id=1))
    captured = {}

    async def fake_get_entity(ref):
        from badking.hybrid.client import Peer

        return Peer(id=7, type="channel")

    async def fake_call(name, **kwargs):
        captured["name"] = name
        # A single message dict — must be wrapped into a list and parsed.
        return {"data": [{"messageId": 42, "message": "salam"}]}

    bot.get_entity = fake_get_entity
    bot.call = fake_call
    bot._parse_message = lambda row, peer: row
    rows = run(bot.get_pinned("@chan"))
    assert captured["name"] == "messaging.LoadPinnedMessages"
    assert rows == [{"messageId": 42, "message": "salam"}]


def test_edit_message_success_does_not_depend_on_nonexistent_response_field():
    """UpdateMessage response is {seq, date}; message_id is not a response field."""
    from badking.hybrid.schema import RESPONSES

    assert "message_id" not in RESPONSES["UpdateMessage"]
    bot = SelfBot(session=Session(access_token="x", user_id=1))

    async def fake_get_entity(ref):
        from badking.hybrid.client import Peer

        return Peer(id=7, type="user")

    async def fake_call(name, **kwargs):
        return {"seq": 1}  # successful minimal response

    bot.get_entity = fake_get_entity
    bot.call = fake_call
    assert run(bot.edit_message(7, 99, "salam")) is True


def test_stop_typing_sends_required_typing_type():
    """aiobale fixture: presence.StopTyping.typing_type (field 2) is required."""
    spec = [m for m in METHODS if m[1] == "StopTyping"][0]
    assert "typing_type" in spec[2]
    bot = SelfBot(session=Session(access_token="x", user_id=1))
    sent = {}

    async def fake_get_entity(ref):
        from badking.hybrid.client import Peer

        return Peer(id=7, type="user")

    async def fake_call(name, **kwargs):
        sent.update(kwargs)

    bot.get_entity = fake_get_entity
    bot.call = fake_call
    run(bot.stop_typing(7))
    assert sent["typing_type"] == 1


def test_set_online_sends_required_timeout():
    """aiobale fixture: presence.SetOnline.timeout (field 2) is required."""
    spec = [m for m in METHODS if m[1] == "SetOnline"][0]
    assert "timeout" in spec[2]
    bot = SelfBot(session=Session(access_token="x", user_id=1))
    sent = {}

    async def fake_call(name, **kwargs):
        sent.update(kwargs)

    bot.call = fake_call
    run(bot.set_online())
    assert sent["is_online"] is True
    assert isinstance(sent["timeout"], int) and sent["timeout"] > 0


# ---------- Security: SSRF ----------

def test_validate_download_url_blocks_loopback_literal():
    for url in (
        "http://127.0.0.1/x",
        "http://[::1]/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/x",
        "http://192.168.1.1/x",
    ):
        with pytest.raises(Exception):
            validate_download_url(url)


def test_validate_download_url_blocks_non_http_schemes():
    for url in ("file:///etc/passwd", "ftp://x.test/a", "javascript:alert(1)"):
        with pytest.raises(Exception):
            validate_download_url(url)


def test_validate_download_url_allows_public_https(monkeypatch):
    import socket
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.158.134.3", port, 0, 0))],
    )
    assert validate_download_url("https://cdn.bale.ai/f/abc") == "https://cdn.bale.ai/f/abc"


# ---------- Security: Windows reserved names ----------

@pytest.mark.parametrize("name", ["CON", "nul", "COM1", "LPT9", "CON.txt", "aux.log"])
def test_sanitize_filename_rejects_windows_reserved_names(name):
    assert sanitize_filename(name) == "file.bin"


def test_sanitize_filename_keeps_normal_names():
    assert sanitize_filename("photo.jpg") == "photo.jpg"
    assert sanitize_filename("../../evil.jpg") == "evil.jpg"


# ---------- Security: deny-by-default for state-changing RPCs ----------

@pytest.mark.parametrize("rpc", [
    "user.EditName", "user.EditAbout", "user.EditNickName", "user.UnblockUser",
    "messaging.ForwardMessages", "messaging.PinMessage", "messaging.UnPinMessages",
    "groups.JoinGroup", "groups.InviteUsers", "groups.GetGroupInviteURL",
    "presence.SetOnline", "presence.Typing", "presence.StopTyping",
    "report.ReportInappropriateContent", "magazine.UpvotePost",
    "abacus.MessageSetReaction", "abacus.MessageRemoveReaction",
])
def test_state_changing_rpc_denied_by_default(rpc):
    with pytest.raises(PermissionDenied):
        PermissionPolicy().check(rpc)


def test_dangerous_rpcs_still_denied():
    for rpc in DANGEROUS_RPCS:
        with pytest.raises(PermissionDenied):
            PermissionPolicy().check(rpc)


def test_explicit_permission_allows_state_changing_rpc():
    PermissionPolicy(allow=frozenset({"manage_contacts"})).check("user.EditName")
    PermissionPolicy(allow=frozenset({"send_messages"})).check("presence.Typing")


def test_readonly_rpc_requires_explicit_read_permission():
    """Deny-by-default شامل خواندن پیامها هم میشود."""
    with pytest.raises(PermissionDenied):
        PermissionPolicy().check("messaging.LoadHistory")
    PermissionPolicy(allow=frozenset({"read_messages"})).check("messaging.LoadHistory")
    # RPC خواندنی که در نقشه نیست (user.LoadUsers) همچنان آزاد است.
    PermissionPolicy().check("user.LoadUsers")


# ---------- Security: no phone number in logs ----------

def test_sessions_debug_log_redacts_phone_key(caplog):
    from badking.hybrid.sessions import _safe_account_label

    label = _safe_account_label("phone:+989123456789")
    assert "989123456789" not in label
    assert label.startswith("<redacted:")


# ---------- Security: doctor masks token fully ----------

def test_doctor_masks_token_prefix(monkeypatch):
    from badking.cli import doctor

    monkeypatch.setenv("BADKING_TOKEN", "123456:SECRET-ABCDEF")
    ok, shown, _ = doctor.check_token()
    assert ok is True
    assert "123456" not in shown
    assert "SECRET" not in shown
    assert shown.endswith("CDEF")


# ---------- Protocol: no guessed fields ----------

def test_media_download_default_max_size_is_bounded():
    assert 0 < DEFAULT_MAX_SIZE <= 4 * 1024**3
