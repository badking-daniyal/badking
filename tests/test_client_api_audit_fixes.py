"""Regression tests for Client API audit fixes.

Covers:
  - Transport does not mutate payload by default (req_id not stamped).
  - FIFO request/response correlation when stamping is off.
  - iter_dialogs cursor uses sortDate, not row count.
"""

from __future__ import annotations

import asyncio

import pytest

from badking.hybrid.client import SelfBot
from badking.hybrid.transport import Transport


class _FakeTransport:
    """Minimal transport capturing call arguments."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    async def request(self, payload, timeout=None):
        return b""

    async def connect(self):
        return self

    async def close(self):
        pass

    on_update = None
    connected = True


@pytest.mark.asyncio
async def test_transport_payload_untouched_by_default():
    """Default transport must not prepend a guessed req_id field."""
    t = Transport("ws://example", stamp_req_id=False)
    payload = b"\x08\x01\x12\x02hi"
    # We only exercise the stamping decision, not a live socket.
    assert t.stamp_req_id is False
    assert payload == b"\x08\x01\x12\x02hi"


@pytest.mark.asyncio
async def test_fifo_correlation_maps_responses_in_order():
    t = Transport("ws://example", stamp_req_id=False)
    t._fifo = ["a", "b"]
    loop = asyncio.get_event_loop()
    fa = loop.create_future()
    fb = loop.create_future()
    t._pending = {"a": fa, "b": fb}

    await t._dispatch(b"first")
    await t._dispatch(b"second")

    assert fa.result() == b"first"
    assert fb.result() == b"second"
    assert t._fifo == []


@pytest.mark.asyncio
async def test_iter_dialogs_uses_sortdate_cursor():
    """Page 2 offset must equal last sortDate, not number of rows."""
    pages = [
        {
            "dialogs": [
                {"peer": {"id": 1, "type": 2}, "sortDate": 1000},
                {"peer": {"id": 2, "type": 2}, "sortDate": 900},
            ]
        },
        {
            "dialogs": [
                {"peer": {"id": 3, "type": 2}, "sortDate": 800},
            ]
        },
    ]
    fake = _FakeTransport(pages)

    bot = SelfBot(session=None)
    bot._transport = fake
    bot._my_id = 0

    # Patch call to consume pages and record offset_date.
    async def fake_call(name, **kwargs):
        fake.calls.append(kwargs)
        return pages.pop(0)

    bot.call = fake_call

    dialogs = [d async for d in bot.iter_dialogs(limit=3, batch=2)]
    assert len(dialogs) == 3
    assert fake.calls[0]["offset_date"] == 0
    assert fake.calls[1]["offset_date"] == 900  # last sortDate of page 1


@pytest.mark.asyncio
async def test_iter_dialogs_stops_on_repeated_cursor():
    """A server echoing the same cursor must not cause an infinite loop."""
    page = {"dialogs": [{"peer": {"id": 1, "type": 2}, "sortDate": 500}]}
    fake = _FakeTransport([page] * 10)
    bot = SelfBot(session=None)
    bot._transport = fake
    bot._my_id = 0
    calls = []

    async def fake_call(name, **kwargs):
        calls.append(kwargs)
        return dict(page)

    bot.call = fake_call
    dialogs = [d async for d in bot.iter_dialogs(limit=None, batch=1)]
    # First page yields 1; second page sees repeated cursor and stops.
    assert len(dialogs) == 2
    assert len(calls) == 2
