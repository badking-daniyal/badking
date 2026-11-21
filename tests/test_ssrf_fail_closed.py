"""تست Fail-Closed — اثبات اینکه شکست DNS هرگز به اتصال بدون Pinning منتهی نمیشود.

قلب این فایل: حتی اگر کد بخواهد AsyncClient معمولی بسازد، ما آن را جاسازی
(Spy) میکنیم تا ثابت شود در شرایط شکست DNS اصلاً AsyncClient ساخته نمیشود.
"""

from __future__ import annotations

import asyncio
import socket

import pytest

from badking.hybrid.client import SelfBot
from badking.hybrid.download import DownloadError
from badking.hybrid.proto import encode_named
from badking.hybrid.rpc import registry


class _FakeTransport:
    def __init__(self, url: str):
        self.url = url

    async def request(self, payload, timeout=None):
        spec = registry.get("files.GetNasimFileUrl")
        inner = encode_named(
            {"fileId": 7, "url": self.url, "timeout": 60000, "chunkSize": 4},
            {"fileId": 1, "url": 2, "timeout": 3, "chunkSize": 7},
        )
        return encode_named({"file_urls": inner}, spec.schema_for_naming())


def _make_bot(url: str):
    bot = SelfBot.__new__(SelfBot)
    bot._transport = _FakeTransport(url)
    bot.timeout = 30.0
    bot.permissions = None
    bot.registry = registry
    bot._my_id = 1
    return bot


def _spy_client(monkeypatch, seen: dict):
    """AsyncClient را جاسازی میکند تا ساخت آن ثبت شود."""
    httpx = pytest.importorskip("httpx")

    class SpyClient:
        def __init__(self, *a, **kw):
            seen["clients_built"] = seen.get("clients_built", 0) + 1
            seen["kwargs"] = kw

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, method, url, **kw):
            raise AssertionError("نباید هیچ درخواستی ارسال شود")

    monkeypatch.setattr(httpx, "AsyncClient", SpyClient)
    return httpx


@pytest.mark.asyncio
async def test_dns_failure_never_builds_unpinned_client(monkeypatch, tmp_path):
    """شکست DNS → DownloadError و صفر AsyncClient بدون pinning."""
    seen: dict = {}
    _spy_client(monkeypatch, seen)

    def fail(host, port):
        raise socket.gaierror("no dns")

    monkeypatch.setattr(socket, "getaddrinfo", fail)

    bot = _make_bot("https://offline.test/f")
    with pytest.raises(DownloadError):
        await bot.download_file(7, 99, destination=tmp_path)

    assert seen.get("clients_built", 0) == 0, "AsyncClient بدون pinning ساخته شد!"


@pytest.mark.asyncio
async def test_empty_dns_never_builds_unpinned_client(monkeypatch, tmp_path):
    """پاسخ DNS خالی → DownloadError و صفر AsyncClient."""
    seen: dict = {}
    _spy_client(monkeypatch, seen)
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port: [])

    bot = _make_bot("https://empty.test/f")
    with pytest.raises(DownloadError):
        await bot.download_file(7, 99, destination=tmp_path)
    assert seen.get("clients_built", 0) == 0


@pytest.mark.asyncio
async def test_private_dns_never_builds_unpinned_client(monkeypatch, tmp_path):
    """DNS به IP خصوصی → DownloadError و صفر AsyncClient."""
    seen: dict = {}
    _spy_client(monkeypatch, seen)
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda h, p: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", p, 0, 0))],
    )

    bot = _make_bot("https://rebind.test/f")
    with pytest.raises(DownloadError):
        await bot.download_file(7, 99, destination=tmp_path)
    assert seen.get("clients_built", 0) == 0


@pytest.mark.asyncio
async def test_redirect_to_bad_dns_never_builds_unpinned_client(monkeypatch, tmp_path):
    """ریدایرکت به دامنهای با DNS نامعتبر → متوقف، بدون اتصال جایگزین."""
    httpx = pytest.importorskip("httpx")
    seen: dict = {}
    calls: list = []

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
            return {"location": "https://offline.test/secret"}

    class Client:
        def __init__(self, *a, **kw):
            assert "transport" in kw, "AsyncClient بدون transport ساخته شد!"
            assert kw.get("trust_env") is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, method, url, **kw):
            calls.append(url)
            return RedirectStream()

    monkeypatch.setattr(httpx, "AsyncClient", Client)

    def fake_dns(host, port):
        if host == "offline.test":
            raise socket.gaierror("no dns")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port, 0, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_dns)

    bot = _make_bot("https://public.test/start")
    with pytest.raises(DownloadError):
        await bot.download_file(7, 99, destination=tmp_path)

    # فقط درخواست اول رفت؛ ریدایرکت به دامنه نامعتبر دنبال نشد.
    assert len(calls) == 1, f"ریدایرکت ناامن دنبال شد: {calls}"


@pytest.mark.asyncio
async def test_cancellation_during_connect_propagates(monkeypatch, tmp_path):
    """Cancellation هنگام اتصال پینشده منتقل میشود و Task باقی نمیماند.

    نکته: ``socket.getaddrinfo`` ذاتاً مسدودکننده و غیرقابل لغو است، پس
    Cancellation هنگام Resolve قابل آزمایش آفلاین نیست (واقعاً BLOCKED است).
    در عوض لغو را روی ``connect_tcp`` بکاند آزمایش میکنیم که واقعاً async است.
    """
    from badking.hybrid import ssrf

    started = asyncio.Event()

    class CancelBackend:
        async def connect_tcp(self, host, port, **kw):
            started.set()
            await asyncio.sleep(10)  # قابل لغو

        async def connect_unix_socket(self, *a, **kw):
            raise AssertionError

        async def sleep(self, seconds):
            await asyncio.sleep(seconds)

    backend = CancelBackend()
    transport = ssrf.PinnedAsyncTransport.__new__(ssrf.PinnedAsyncTransport)
    import httpcore
    transport._pool = httpcore.AsyncConnectionPool(network_backend=backend)
    transport._closed = False

    async def run():
        req = httpcore.Request(
            method="GET",
            url=httpcore.URL(scheme="http", host=b"cdn.test", port=80, target="/f"),
            headers=[(b"host", b"cdn.test")],
        )
        return await transport._pool.handle_async_request(req)

    task = asyncio.create_task(run())
    await asyncio.wait_for(started.wait(), timeout=2.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.done()
    await transport.aclose()


@pytest.mark.asyncio
async def test_no_leftover_tasks_after_failures(monkeypatch, tmp_path):
    """پس از شکستهای مکرر DNS، هیچ Task باقی نمیماند."""
    before = {t for t in asyncio.all_tasks() if t is not asyncio.current_task()}
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, p: (_ for _ in ()).throw(socket.gaierror("x")))

    bot = _make_bot("https://offline.test/f")
    for _ in range(5):
        with pytest.raises(DownloadError):
            await bot.download_file(7, 99, destination=tmp_path)

    await asyncio.sleep(0)
    after = {t for t in asyncio.all_tasks() if t is not asyncio.current_task()}
    assert after == before, "Task باقیمانده پس از شکست DNS"
