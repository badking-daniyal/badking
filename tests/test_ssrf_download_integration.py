"""تست یکپارچگی مسیر download_file — اثبات IP Pinning در جریان واقعی دانلود.

نشان میدهد ``SelfBot.download_file`` واقعاً transport پینشده میسازد و
proxy محیطی را خاموش میکند، نه اینکه فقط تابع validate را صدا بزند.
"""

from __future__ import annotations

import socket

import pytest

from badking.hybrid.client import SelfBot
from badking.hybrid.proto import encode_named
from badking.hybrid.rpc import registry


class _FakeTransport:
    async def request(self, payload, timeout=None):
        spec = registry.get("files.GetNasimFileUrl")
        inner = encode_named(
            {"fileId": 7, "url": "https://cdn.test/f", "timeout": 60000, "chunkSize": 4},
            {"fileId": 1, "url": 2, "timeout": 3, "chunkSize": 7},
        )
        return encode_named({"file_urls": inner}, spec.schema_for_naming())


@pytest.mark.asyncio
async def test_download_file_builds_pinned_transport(monkeypatch, tmp_path):
    httpx = pytest.importorskip("httpx")

    seen: dict = {}

    def fake_dns(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port, 0, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_dns)

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        async def aiter_bytes(self, chunk_size=65536):
            yield b"OK"

    class FakeClient:
        def __init__(self, *a, **kw):
            seen["kwargs"] = kw

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, method, url, **kw):
            return FakeStream()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    bot = SelfBot.__new__(SelfBot)
    bot._transport = _FakeTransport()
    bot.timeout = 30.0
    bot.permissions = None
    bot.registry = registry
    bot._my_id = 1

    out = await bot.download_file(7, 99, destination=tmp_path)
    assert out.read_bytes() == b"OK"

    transport = seen["kwargs"].get("transport")
    assert transport is not None
    assert type(transport).__name__ == "PinnedAsyncTransport"
    assert transport._pool._network_backend._pinned_ip == "8.8.8.8"
    assert seen["kwargs"].get("trust_env") is False
    assert seen["kwargs"].get("follow_redirects") is False


@pytest.mark.asyncio
async def test_download_file_redirect_revalidates_and_repins(monkeypatch, tmp_path):
    """ریدایرکت به IP خصوصی حتی در میانه دانلود مسدود میشود."""
    httpx = pytest.importorskip("httpx")

    def fake_dns(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port, 0, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_dns)

    class RedirectStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        @property
        def status_code(self):
            return 302

        @property
        def headers(self):
            return {"location": "http://127.0.0.1/secret"}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, method, url, **kw):
            return RedirectStream()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    bot = SelfBot.__new__(SelfBot)
    bot._transport = _FakeTransport()
    bot.timeout = 30.0
    bot.permissions = None
    bot.registry = registry
    bot._my_id = 1

    from badking.hybrid.download import DownloadError

    with pytest.raises(DownloadError):
        await bot.download_file(7, 99, destination=tmp_path)
