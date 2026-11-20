"""تست Self Client Reliability — خطا، flood wait، correlation، shutdown."""

from __future__ import annotations

import asyncio

import pytest

from badking.hybrid.proto import build
from badking.hybrid.reliability import (
    ERROR_CODE_FIELD,
    ERROR_MESSAGE_FIELD,
    RETRY_AFTER_FIELD,
    RpcErrorInfo,
    parse_rpc_error,
    raise_for_rpc_error,
)
from badking.hybrid.transport import (
    RpcFailed,
    RpcTimeout,
    TransportError,
    _peek_req_id,
    _stamp_req_id,
    frame_length_prefixed,
    frame_raw,
    unframe_length_prefixed,
    unframe_raw,
)


class TestFraming:
    @pytest.mark.parametrize("frame,unframe", [
        (frame_length_prefixed, unframe_length_prefixed),
        (frame_raw, unframe_raw),
    ])
    def test_single_frame(self, frame, unframe):
        payload = b"hello world"
        frames, rest = unframe(frame(payload))
        assert payload in frames
        assert rest == b""

    def test_partial_frame_buffered(self):
        framed = frame_length_prefixed(b"abcdef")
        first, rest = unframe_length_prefixed(framed[:3])
        assert first == []
        second, rest2 = unframe_length_prefixed(rest + framed[3:])
        assert b"abcdef" in second

    def test_two_frames_in_one_chunk(self):
        data = frame_length_prefixed(b"one") + frame_length_prefixed(b"two")
        frames, rest = unframe_length_prefixed(data)
        assert b"one" in frames and b"two" in frames
        assert rest == b""


class TestRequestCorrelation:
    def test_stamp_and_peek(self):
        stamped = _stamp_req_id(b"payload", "1f")
        assert _peek_req_id(stamped) == "1f"

    def test_different_ids(self):
        for rid in ("1", "ff", "a3b"):
            assert _peek_req_id(_stamp_req_id(b"x", rid)) == rid

    def test_malformed_returns_none(self):
        # varint ناتمام → None
        assert _peek_req_id(b"\x08") is None

    def test_non_req_id_field_returns_none(self):
        # فیلد 2 (tag 0x10) نباید بهعنوان req_id خوانده شود
        assert _peek_req_id(b"\x10\x01") is None


class TestRpcErrorMapping:
    def test_no_error(self):
        assert parse_rpc_error(build({1: 42})) is None

    def test_error_extracted(self):
        frame = build({
            ERROR_CODE_FIELD: 429,
            ERROR_MESSAGE_FIELD: "too many requests",
            RETRY_AFTER_FIELD: 5,
        })
        info = parse_rpc_error(frame)
        assert info is not None
        assert info.code == 429
        assert info.retry_after == 5.0
        assert info.is_flood

    def test_auth_error(self):
        frame = build({ERROR_CODE_FIELD: 401, ERROR_MESSAGE_FIELD: "unauthorized"})
        info = parse_rpc_error(frame)
        assert info.is_auth
        assert not info.is_flood

    def test_server_error(self):
        frame = build({ERROR_CODE_FIELD: 503})
        assert parse_rpc_error(frame).is_server

    def test_raise(self):
        frame = build({ERROR_CODE_FIELD: 429, RETRY_AFTER_FIELD: 3})
        with pytest.raises(RpcFailed) as exc:
            raise_for_rpc_error(frame)
        assert exc.value.code == 429
        assert exc.value.retry_after == 3.0

    def test_no_raise_on_success(self):
        raise_for_rpc_error(build({1: 1}))  # no exception


class TestClientErrorIntegration:
    def test_call_raises_on_server_error(self):
        from badking.hybrid import SelfBot
        from badking.hybrid.session import Session
        from badking.hybrid.security import PermissionPolicy

        bot = SelfBot(
            session=Session(access_token="x", user_id=1),
            permissions=PermissionPolicy.full(),
        )

        class FakeTransport:
            async def request(self, payload, timeout=None):
                return build({ERROR_CODE_FIELD: 429, RETRY_AFTER_FIELD: 2})

        bot._transport = FakeTransport()
        with pytest.raises(RpcFailed) as exc:
            asyncio.get_event_loop().run_until_complete(
                bot.call("messaging.SendMessage",
                         peer={}, message_id=1, content={}, chat={})
            )
        assert exc.value.retry_after == 2.0


class TestTimeoutAndShutdown:
    def test_rpc_timeout_type(self):
        assert issubclass(RpcTimeout, TransportError)

    def test_graceful_close_is_idempotent(self):
        """close() دو بار خطا ندهد."""
        from badking.hybrid.transport import Transport

        # بدون اتصال واقعی — فقط منطق close
        t = object.__new__(Transport)
        t._closed = False
        t._reader_task = None
        t._ws = None
        t._pending = {}
        asyncio.get_event_loop().run_until_complete(t.close())
        asyncio.get_event_loop().run_until_complete(t.close())
        assert t._closed is True
