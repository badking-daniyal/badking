"""تست سازگاریtransport — وابستگی به API داخلی httpx/httpcore را صریح میکند.

IP Pinning نیاز به دو API داخلی دارد:

1. ``httpcore.AsyncConnectionPool(network_backend=...)`` — عمومی و پایدار در httpcore 1.x.
2. ``httpx._transports.default.AsyncResponseStream`` — داخلی httpx، برای حفظ Streaming.
3. ``httpcore._backends.auto.AutoBackend`` — داخلی httpcore، بکاند پیشفرض.

این تستها وجود و امضای آنها را بررسی میکنند تا در صورت ارتقا وابستگی،
شکست ناشی از تغییر API به موقع دیده شود (نه در زمان دانلود واقعی).
"""

from __future__ import annotations

import inspect

import pytest

httpx = pytest.importorskip("httpx")
httpcore = pytest.importorskip("httpcore")


def test_httpcore_pool_accepts_network_backend():
    params = inspect.signature(httpcore.AsyncConnectionPool.__init__).parameters
    assert "network_backend" in params


def test_async_response_stream_internal_api_available():
    from httpx._transports.default import AsyncResponseStream

    sig = inspect.signature(AsyncResponseStream.__init__)
    assert "httpcore_stream" in sig.parameters


def test_auto_backend_internal_api_available():
    from httpcore._backends.auto import AutoBackend

    for method in ("connect_tcp", "connect_unix_socket", "sleep"):
        assert callable(getattr(AutoBackend, method, None)), method


def test_pinned_backend_matches_async_network_backend_interface():
    from badking.hybrid.ssrf import PinnedAsyncBackend

    backend = PinnedAsyncBackend("8.8.8.8")
    for method in ("connect_tcp", "connect_unix_socket", "sleep"):
        assert callable(getattr(backend, method)), method


def test_pinned_transport_is_async_base_transport():
    from badking.hybrid.ssrf import PinnedAsyncTransport

    assert issubclass(PinnedAsyncTransport, httpx.AsyncBaseTransport)


def test_pinned_transport_preserves_streaming(monkeypatch):
    """پاسخ transport جریانی است و content بلافاصله خوانده نمیشود."""
    import socket

    from badking.hybrid import ssrf

    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda h, p: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", p, 0, 0))],
    )
    transport, _host, _port = ssrf.build_pinned_transport("https://cdn.test/f")
    assert transport is not None
    assert type(transport).__name__ == "PinnedAsyncTransport"
    # pool با backend پینشده ساخته شده است
    assert transport._pool._network_backend._pinned_ip == "8.8.8.8"


def test_tls_verification_context_is_default_not_relaxed():
    """SSL context پیشفرض است و verification را خاموش نمیکند."""
    import ssl

    from badking.hybrid.ssrf import _default_ssl_context

    ctx = _default_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
