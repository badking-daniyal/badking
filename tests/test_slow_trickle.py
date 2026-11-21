"""Slow HTTP Trickle protection — deadline on streaming writes.

A server that sends one byte every few seconds defeats per-operation
httpx timeouts. ``write_stream_atomic(deadline=...)`` imposes an absolute
wall-clock budget. No protocol/RPC guessing involved.
"""

from __future__ import annotations

import asyncio

import pytest

from badking.hybrid.download import DownloadError, write_stream_atomic


async def _trickle(chunks, delay: float):
    for chunk in chunks:
        await asyncio.sleep(delay)
        yield chunk


def test_deadline_stops_slow_trickle(tmp_path):
    target = tmp_path / "slow.bin"

    async def run():
        return await write_stream_atomic(
            _trickle([b"a", b"b", b"c"], delay=0.03),
            target,
            deadline=0.05,  # only the first chunk fits
        )

    with pytest.raises(DownloadError, match="زمان دانلود"):
        asyncio.get_event_loop().run_until_complete(run())
    # partial file must be cleaned up, destination never created
    assert not target.exists()
    assert list(tmp_path.glob("*.part")) == []
    assert list(tmp_path.glob(".*.part")) == []


def test_deadline_none_keeps_old_behavior(tmp_path):
    target = tmp_path / "ok.bin"

    async def run():
        return await write_stream_atomic(
            _trickle([b"x", b"y"], delay=0.001),
            target,
            deadline=None,
        )

    written = asyncio.get_event_loop().run_until_complete(run())
    assert written == 2
    assert target.read_bytes() == b"xy"


def test_deadline_generous_allows_normal_stream(tmp_path):
    target = tmp_path / "ok2.bin"

    async def run():
        return await write_stream_atomic(
            _trickle([b"a" * 100, b"b" * 100], delay=0.001),
            target,
            deadline=5.0,
        )

    written = asyncio.get_event_loop().run_until_complete(run())
    assert written == 200
    assert target.read_bytes() == b"a" * 100 + b"b" * 100


def test_deadline_does_not_touch_existing_destination(tmp_path):
    target = tmp_path / "existing.bin"
    target.write_bytes(b"ORIGINAL")

    async def run():
        return await write_stream_atomic(
            _trickle([b"new", b"more"], delay=0.04),
            target,
            deadline=0.05,
        )

    with pytest.raises(DownloadError):
        asyncio.get_event_loop().run_until_complete(run())
    assert target.read_bytes() == b"ORIGINAL"
