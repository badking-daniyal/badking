"""IP Pinning برای دانلود رسانه — محافظت واقعی در برابر DNS Rebinding.

ایده:

* ``validate_download_url`` تنها IPها را بررسی میکند، ولی httpx هنگام اتصال
  دوباره DNS resolve میکند. بین این دو فاصله زمانی وجود دارد و DNS میتواند
  تغییر کند (DNS rebinding).
* در اینجا ``connect_tcp`` سطح httpcore را طوری هدایت میکنیم که به جای
  hostname، دقیقاً به IP تأییدشده وصل شود. hostname اصلی در ``Origin``
  باقی میماند، بنابراین httpcore همان hostname را برای:

  - هدر ``Host`` (و ``:authority`` در HTTP/2)، و
  - ``server_hostname`` در TLS (یعنی SNI و اعتبارسنجی گواهی)

  استفاده میکند. به عبارت دیگر IP پین میشود ولی TLS/SNI دستکاری نمیشود.

این ماژول وابستگی جدیدی اضافه نمیکند: httpx و httpcore پیشتر وابستگی
دانلود بودهاند. تمام کلاسها در صورت نبود httpx/httpcore بهصورت ایمن import
می_shوند (ImportError در ``download_file`` مدیریت شده است).
"""

from __future__ import annotations

from typing import Any, Iterable

from .download import DownloadError, resolve_validated_ips

try:  # pragma: no cover — بسته به محیط نصب است
    import httpcore
    import httpx
except ImportError:  # pragma: no cover
    httpcore = None  # type: ignore[assignment]
    httpx = None  # type: ignore[assignment]


class PinnedAsyncBackend:
    """``AsyncNetworkBackend`` که اتصال TCP را به IP تأییدشده هدایت میکند.

    تمام متدها همان امضای ``httpcore.AsyncNetworkBackend`` را دارند تا
    جایگزین مستقیم AutoBackend باشد.

    Args:
        pinned_ip: IPای که قبلاً توسط ``resolve_validated_ips`` تأیید شده است.
    """

    def __init__(self, pinned_ip: str) -> None:
        self._pinned_ip = pinned_ip
        self._inner: Any = None

    def _backend(self) -> Any:
        if self._inner is None:
            # AutoBackend بسته به trio/asyncio بکاند مناسب را انتخاب میکند.
            # در httpcore 1.x این کلاس در namespace اصلی صادر نمیشود.
            try:
                from httpcore._backends.auto import AutoBackend
            except ImportError:  # pragma: no cover — نسخههای قدیمتر
                AutoBackend = httpcore.AutoBackend  # type: ignore[union-attr]
            self._inner = AutoBackend()
        return self._inner

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> Any:
        # host (hostname اصلی) عمداً نادیده گرفته میشود. Origin در httpcore
        # همان hostname باقی میماند، پس Host/SNI تغییر نمیکند.
        return await self._backend().connect_tcp(
            self._pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> Any:  # pragma: no cover — دانلود از UNIX socket استفاده نمیکند
        raise DownloadError("اتصال UNIX socket در دانلود مجاز نیست")

    async def sleep(self, seconds: float) -> None:
        await self._backend().sleep(seconds)


class PinnedAsyncTransport:
    """``httpx.AsyncBaseTransport`` مبتنی بر pool با IP پینشده.

    ``trust_env=False`` است تا متغیرهای ``HTTP_PROXY`` / ``HTTPS_PROXY`` /
    ``ALL_PROXY`` نتوانند اتصال را از مسیر پینشده دور بزنند.
    """

    def __init__(
        self,
        pinned_ip: str,
        *,
        verify: bool = True,
        timeout: float | None = None,
    ) -> None:
        if httpcore is None or httpx is None:  # pragma: no cover
            raise DownloadError("برای IP Pinning به httpx/httpcore نیاز است")
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=None if not verify else _default_ssl_context(),
            network_backend=PinnedAsyncBackend(pinned_ip),
        )
        self._closed = False

    async def handle_async_request(self, request: Any) -> Any:
        if self._closed:
            raise DownloadError("transport دانلود بسته شده است")
        # httpcore Origin از request.url میآید، نه از آدرس IP بکاند.
        core_request = httpcore.Request(  # type: ignore[union-attr]
            method=request.method,
            url=httpcore.URL(  # type: ignore[union-attr]
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        core_response = await self._pool.handle_async_request(core_request)
        # همان الگوی httpx.AsyncHTTPTransport: پاسخ httpcore جریانی است،
        # نباید content آن را بلافاصله خواند (جریان دانلود حفظ میشود).
        from httpx._transports.default import AsyncResponseStream  # type: ignore

        return httpx.Response(  # type: ignore[union-attr]
            status_code=core_response.status,
            headers=core_response.headers,
            stream=AsyncResponseStream(core_response.stream),
            extensions=core_response.extensions,
            request=request,
        )

    async def __aenter__(self) -> "PinnedAsyncTransport":
        await self._pool.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            await self._pool.aclose()


def _default_ssl_context():  # pragma: no cover — توسط stdlib تأمین میشود
    """SSL context پیشفرض با verification عادی (عدم دستکاری TLS)."""
    import ssl

    ctx = ssl.create_default_context()
    return ctx


def build_pinned_transport(url: str, *, verify: bool = True) -> Any:
    """URL را اعتبارسنجی و transportای بسازد که به IP تأییدشده وصل شود.

    Returns:
        ``(transport, host, port)`` — transport آماده برای ``httpx.AsyncClient``.
    """
    host, port, ips = resolve_validated_ips(url)
    if not ips:
        # DNS دردسترس نبود؛ نمیتوان پین کرد. فراخواننده باید از حالت
        # معمولی (بدون pinning) استفاده کند — در محیط واقعی با DNS سالم
        # این حالت رخ نمیدهد.
        return None, host, port
    # اگر چند IP وجود دارد، تمام آنها قبلاً توسط resolve_validated_ips
    # اعتبارسنجی شدهاند. ما به اولین IP میپینیم تا همان IP تأییدشده استفاده
    # شود (هیچ resolve مجددی در مسیر اتصال رخ نمیدهد).
    transport = PinnedAsyncTransport(ips[0], verify=verify)
    return transport, host, port
