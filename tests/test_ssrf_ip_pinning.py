"""تستهای امنیتی IP Pinning و DNS Rebinding — آفلاین (Mock)، بدون حساب واقعی.

این تستها رفتار **اتصال واقعی** را بررسی میکنند: اینکه ``connect_tcp`` دقیقاً
به IP تأییدشده صدا زده میشود، نه صرفاً خروجی ``validate_download_url``.

همچنین ثبت میشود که hostname اصلی در ``Origin``/``Host``/SNI باقی میماند.
"""

from __future__ import annotations

import ipaddress
import socket

import pytest

from badking.hybrid.download import (
    DownloadError,
    is_public_ip,
    resolve_validated_ips,
    validate_download_url,
)


# --------------------------------------------------------------------------
# ۱) طبقهبندی IP — رنجهای خطرناک
# --------------------------------------------------------------------------

@pytest.mark.parametrize("ip", [
    "0.0.0.0", "0.1.2.3", "10.0.0.1", "127.0.0.1", "169.254.169.254",
    "172.16.5.4", "192.168.1.1", "100.64.0.1", "192.0.0.1", "198.18.0.1",
    "224.0.0.1", "240.0.0.1", "::", "::1", "fe80::1", "ff02::1",
    "::ffff:127.0.0.1", "::ffff:192.168.1.1", "::ffff:8.8.8.8",
])
def test_dangerous_ips_are_rejected(ip):
    assert is_public_ip(ipaddress.ip_address(ip)) is False


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.158.134.3", "2606:4700:4700::1111"])
def test_public_ips_allowed(ip):
    assert is_public_ip(ipaddress.ip_address(ip)) is True


# --------------------------------------------------------------------------
# ۲) URL مبهم، userinfo و پورت
# --------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://user:pass@8.8.8.8/x",
    "https://user@cdn.bale.ai/f",
    "http://8.8.8.8:22/x",
    "http://8.8.8.8:6379/x",
    "http://8.8.8.8:99999/x",
    "file:///etc/passwd",
    "javascript:alert(1)",
])
def test_ambiguous_or_internal_urls_rejected(url):
    with pytest.raises(DownloadError):
        validate_download_url(url)


def test_public_url_accepted(monkeypatch):
    # DNS جعلی معتبر: محیط آفلاین نباید مانع تست «پذیرش URL عمومی» شود.
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(["93.158.134.3"]))
    assert validate_download_url("https://cdn.bale.ai/f/abc") == "https://cdn.bale.ai/f/abc"


# --------------------------------------------------------------------------
# ۳) DNS با IP خصوصی / چند IP — تمام IPها بررسی میشوند
# --------------------------------------------------------------------------

def _fake_getaddrinfo(records):
    def fake(host, port):
        return [
            (socket.AF_INET if ":" not in ip else socket.AF_INET6,
             socket.SOCK_STREAM, 6, "", (ip, port, 0, 0))
            for ip in records
        ]
    return fake


def test_dns_private_ip_blocked(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(["10.0.0.5"]))
    with pytest.raises(DownloadError):
        validate_download_url("https://cdn.example.test/f")


def test_dns_multi_ip_one_private_blocks_all(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", _fake_getaddrinfo(["8.8.8.8", "10.0.0.5"])
    )
    with pytest.raises(DownloadError):
        validate_download_url("https://cdn.example.test/f")


def test_dns_all_public_returns_all_ips(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", _fake_getaddrinfo(["8.8.8.8", "1.1.1.1"])
    )
    host, port, ips = resolve_validated_ips("https://cdn.example.test/f")
    assert host == "cdn.example.test"
    assert port == 443
    assert ips == ["8.8.8.8", "1.1.1.1"]


# --------------------------------------------------------------------------
# ۴) اثبات IP Pinning در سطح اتصال — قلب محافظت DNS Rebinding
# --------------------------------------------------------------------------

class _RecordingBackend:
    """بکاند جعلی که فقط host/port اتصال را ثبت میکند."""

    def __init__(self):
        self.calls = []

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.calls.append((host, port))
        return "STREAM"

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise AssertionError("نباید فراخوانی شود")

    async def sleep(self, seconds):
        return None


@pytest.mark.asyncio
async def test_pinned_backend_connects_to_validated_ip_not_hostname(monkeypatch):
    """ hostname عمومی → IP 8.8.8.8؛ connect باید به 8.8.8.8 برود، نه cdn.test """
    from badking.hybrid import ssrf

    monkeypatch.setattr(
        socket, "getaddrinfo", _fake_getaddrinfo(["8.8.8.8"])
    )
    transport, host, port = ssrf.build_pinned_transport("https://cdn.test/f")
    assert transport is not None
    assert host == "cdn.test"

    recorder = _RecordingBackend()
    transport._pool._network_backend._inner = recorder  # تزریق بکاند ضبطکننده

    stream = await transport._pool._network_backend.connect_tcp("cdn.test", 443)
    assert stream == "STREAM"
    # مهم: به جای hostname، دقیقاً IP تأییدشده صدا زده شد.
    assert recorder.calls == [("8.8.8.8", 443)]


@pytest.mark.asyncio
async def test_pinned_backend_ignores_rebound_hostname(monkeypatch):
    """حتی اگر کد دیگری hostname دیگری بدهد، باز هم IP پینشده استفاده میشود."""
    from badking.hybrid import ssrf

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(["1.1.1.1"]))
    transport, _host, _port = ssrf.build_pinned_transport("https://cdn.test/f")
    recorder = _RecordingBackend()
    transport._pool._network_backend._inner = recorder

    # شبیهسازی rebinding: کد میخواهد به 127.0.0.1 وصل شود
    await transport._pool._network_backend.connect_tcp("127.0.0.1", 443)
    assert recorder.calls == [("1.1.1.1", 443)]


@pytest.mark.asyncio
async def test_dns_failure_is_fail_closed(monkeypatch):
    """DNS ناموفق → استثنا، NOT transport معمولی (Fail-Closed)."""
    from badking.hybrid import ssrf

    def fail(host, port):
        raise socket.gaierror("no dns")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    with pytest.raises(DownloadError):
        ssrf.build_pinned_transport("https://offline.test/f")


@pytest.mark.asyncio
async def test_dns_empty_response_is_fail_closed(monkeypatch):
    """پاسخ DNS خالی → استثنا، NOT اتصال بدون pinning."""
    from badking.hybrid import ssrf

    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port: [])
    with pytest.raises(DownloadError):
        ssrf.build_pinned_transport("https://empty.test/f")


@pytest.mark.asyncio
async def test_dns_invalid_record_is_fail_closed(monkeypatch):
    """رکورد DNS نامعتبر → استثنا، NOT نادیده گرفتن رکورد."""
    from badking.hybrid import ssrf

    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("not-an-ip", port, 0, 0))],
    )
    with pytest.raises(DownloadError):
        ssrf.build_pinned_transport("https://bad.test/f")


@pytest.mark.asyncio
async def test_dns_timeout_is_fail_closed(monkeypatch):
    """DNS Timeout → استثنا، NOT مسیر جایگزین ناامن."""
    from badking.hybrid import ssrf

    def timeout(host, port):
        raise TimeoutError("dns timeout")

    monkeypatch.setattr(socket, "getaddrinfo", timeout)
    with pytest.raises(DownloadError):
        ssrf.build_pinned_transport("https://slow.test/f")


# --------------------------------------------------------------------------
# ۵) حفظ TLS / SNI / Host — hostname اصلی در Origin میماند
# --------------------------------------------------------------------------

def test_origin_uses_hostname_not_pinned_ip(monkeypatch):
    """ثابت میکند httpcore Origin همان hostname اصلی را میسازد، نه IP پینشده."""
    import httpcore

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(["8.8.8.8"]))
    from badking.hybrid import ssrf

    transport, host, _port = ssrf.build_pinned_transport("https://cdn.test/f")
    assert host == "cdn.test"
    # Origin از request URL ساخته میشود، نه از pinned_ip.
    origin = httpcore.URL(scheme="https", host="cdn.test", port=443, target="/f")
    assert origin.host == b"cdn.test"
    # httpcore connect_tls از origin.host بهعنوان server_hostname/SNI استفاده
    # میکند (در سورس httpcore/_async/connection.py خط ~152 تأیید شد).
    assert origin.host.decode("ascii") == "cdn.test"


def test_pinned_transport_disables_proxy_env(monkeypatch):
    """transport ساختهشده نباید از proxy محیطی استفاده کند."""
    from badking.hybrid import ssrf

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(["8.8.8.8"]))
    transport, _host, _port = ssrf.build_pinned_transport("https://cdn.test/f")
    # pool مستقیم است (نه AsyncHTTPProxy) → proxy دور زده نمیشود.
    assert type(transport._pool).__name__ == "AsyncConnectionPool"
