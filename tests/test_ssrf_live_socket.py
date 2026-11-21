"""تست اتصال واقعی Socket/IP Pinning — آفلاین (سرور محلی، بدون اینترنت و حساب).

برخلاف تستهای Mock، اینجا یک سرور HTTP واقعی روی 127.0.0.2 گوش میدهد و
ما hostname جعلی ``cdn.test`` را در DNS جعل میکنیم تا به 127.0.0.1 بگوید.
سپس IP پینشده را 127.0.0.2 قرار میدهیم:

* اگر اتصال به 127.0.0.2 رسید → IP Pinning واقعی است (rebinding بیاثر شد).
* اگر سرور هدر ``Host: cdn.test`` را دید → hostname اصلی حفظ شده (SNI/Host).

روی Windows ممکن است 127.0.0.2 قابل bind نباشد؛ در آن صورت تست SKIP میشود.
"""

from __future__ import annotations

import asyncio
import socket
import threading

import pytest

httpx = pytest.importorskip("httpx")
httpcore = pytest.importorskip("httpcore")

from badking.hybrid.ssrf import (  # noqa: E402
    PinnedAsyncBackend,
    PinnedAsyncTransport,
)


def _bind_server(host: str):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((host, 0))
    except OSError:
        srv.close()
        return None, None
    srv.listen(1)
    return srv, srv.getsockname()[1]


def _serve_once(srv, seen: dict):
    try:
        conn, _addr = srv.accept()
    except OSError:
        return
    with conn:
        conn.settimeout(3.0)
        try:
            data = b""
            while b"\r\n\r\n" not in data and len(data) < 8192:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            seen["request"] = data.decode("latin-1", "replace")
            body = b"PINNED-OK"
            conn.sendall(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n" + body
            )
        except OSError as exc:
            seen["error"] = str(exc)
    srv.close()


@pytest.mark.asyncio
async def test_real_socket_uses_pinned_ip_and_keeps_host_header(monkeypatch):
    # سرور واقعی روی 127.0.0.2 (مقصد پینشده)، نه 127.0.0.1 (نتیجه DNS جعلی).
    srv, port = _bind_server("127.0.0.2")
    if srv is None:
        pytest.skip("127.0.0.2 قابل bind نیست روی این سیستم")

    seen: dict = {}
    t = threading.Thread(target=_serve_once, args=(srv, seen), daemon=True)
    t.start()

    # DNS جعلی: cdn.test → 127.0.0.1 (حمله rebinding)
    def fake_getaddrinfo(host, p):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", p, 0, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    # IP پینشده = 127.0.0.2 (همان جایی که سرور گوش میدهد)
    backend = PinnedAsyncBackend("127.0.0.2")
    pool = httpcore.AsyncConnectionPool(network_backend=backend)
    transport = PinnedAsyncTransport.__new__(PinnedAsyncTransport)
    transport._pool = pool
    transport._closed = False

    url = f"http://cdn.test:{port}/f"
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        resp = await client.get(url, timeout=5.0)

    t.join(timeout=5.0)

    assert resp.status_code == 200
    assert resp.text == "PINNED-OK"
    request = seen.get("request", "")
    # اثبات Host حفظ شده: سرور Host: cdn.test:port دید، نه 127.0.0.2.
    assert "cdn.test" in request.lower(), f"Host header حفظ نشد: {request[:200]!r}"
    assert "127.0.0.2" not in request.lower()
    await transport.aclose()
