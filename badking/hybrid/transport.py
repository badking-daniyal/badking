"""Transport: لایه شبکه self-bot روی WebSocket.

این ماژول مسئول چهار چیز است:
    1. اتصال WebSocket با هدرهای احراز هویت
    2. قاب‌بندی (framing) پیام‌ها روی سوکت
    3. تطبیق درخواست/پاسخ با شناسه
    4. اتصال مجدد خودکار و صف‌بندی درخواست‌های در جریان

پروتکل بله بسته است، بنابراین قاب‌بندی اینجا قابل تنظیم است: طول‌دار
(4 بایت big-endian) یا خام. پیش‌فرض طول‌دار است چون اکثر پیاده‌سازی‌های
gRPC-over-WebSocket همین را دارند، ولی اگر فرق داشت با `framing=` عوض کن.

هشدار: غیررسمی. ممکن است بدون اطلاع بشکند.
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger("badking.hybrid.transport")

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore
    WebSocketClientProtocol = Any  # type: ignore


class TransportError(Exception):
    """خطای پایه transport."""


class NotConnected(TransportError):
    """سوکت بسته است."""


class RpcTimeout(TransportError):
    """پاسخ در مهلت نرسید."""


class RpcFailed(TransportError):
    """سرور خطا برگرداند."""

    def __init__(self, message: str, code: int = 0, retry_after: float | None = None):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


# ---------- قاب‌بندی ----------
def frame_length_prefixed(payload: bytes) -> bytes:
    """4 بایت طول big-endian + payload."""
    return struct.pack(">I", len(payload)) + payload


def unframe_length_prefixed(buf: bytes) -> tuple[list[bytes], bytes]:
    """جدا کردن پیام‌های کامل از بافر. برمی‌گرداند (پیام‌ها، باقی‌مانده)."""
    out: list[bytes] = []
    pos = 0
    while len(buf) - pos >= 4:
        (length,) = struct.unpack(">I", buf[pos:pos + 4])
        if length > 64 * 1024 * 1024:
            raise TransportError(f"قاب بیش از حد بزرگ: {length}")
        if len(buf) - pos - 4 < length:
            break
        out.append(buf[pos + 4:pos + 4 + length])
        pos += 4 + length
    return out, buf[pos:]


def frame_raw(payload: bytes) -> bytes:
    return payload


def unframe_raw(buf: bytes) -> tuple[list[bytes], bytes]:
    if not buf:
        return [], b""
    return [buf], b""


FRAMINGS = {
    "length": (frame_length_prefixed, unframe_length_prefixed),
    "raw": (frame_raw, unframe_raw),
}


@dataclass
class RateState:
    """وضعیت محدودیت نرخ که از سرور یاد گرفته می‌شود."""

    min_interval: float = 0.0
    last_sent: float = 0.0
    penalty_until: float = 0.0
    observed_retry_after: list[float] = field(default_factory=list)

    def wait_needed(self) -> float:
        now = time.monotonic()
        wait = 0.0
        if self.penalty_until > now:
            wait = self.penalty_until - now
        gap = now - self.last_sent
        if self.min_interval > gap:
            wait = max(wait, self.min_interval - gap)
        return wait

    def note_sent(self) -> None:
        self.last_sent = time.monotonic()

    def learn(self, retry_after: float) -> None:
        """یادگیری از retry_after سرور: فاصله مجاز را بالا ببر."""
        self.observed_retry_after.append(retry_after)
        if len(self.observed_retry_after) > 20:
            self.observed_retry_after.pop(0)
        self.penalty_until = time.monotonic() + retry_after
        # فاصله پایه را تدریجاً بالا ببر تا دوباره نخوریم
        self.min_interval = max(self.min_interval, min(retry_after / 4.0, 2.0))


class Transport:
    """اتصال WebSocket با تطبیق درخواست/پاسخ.

    سرور پیام‌ها را با یک شناسه (`req_id`) برمی‌گرداند. این کلاس یک
    Future برای هر شناسه نگه می‌دارد و پاسخ را به آن تحویل می‌دهد.
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        framing: str = "length",
        timeout: float = 30.0,
        max_reconnect: int = 5,
        ping_interval: float = 25.0,
    ):
        if websockets is None:  # pragma: no cover
            raise TransportError(
                "websockets نصب نیست. اجرا کن: pip install badking[hybrid]"
            )
        if framing not in FRAMINGS:
            raise TransportError(f"framing ناشناخته: {framing}")
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.max_reconnect = max_reconnect
        self.ping_interval = ping_interval
        self._frame, self._unframe = FRAMINGS[framing]
        self._ws: Any = None
        self._buf = b""
        self._pending: dict[str, asyncio.Future] = {}
        self._seq = 0
        self._reader_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self.rate = RateState()
        self.on_update: Callable[[bytes], Awaitable[None]] | None = None
        self.on_disconnect: Callable[[], Awaitable[None]] | None = None
        self._closed = False
        self.stats = {"sent": 0, "received": 0, "reconnects": 0, "errors": 0}

    # ---------- چرخه حیات ----------
    async def connect(self) -> None:
        """باز کردن سوکت و شروع خواننده."""
        self._closed = False
        self._ws = await websockets.connect(
            self.url,
            extra_headers=self.headers,
            ping_interval=self.ping_interval,
            max_size=64 * 1024 * 1024,
        )
        self._buf = b""
        self._reader_task = asyncio.create_task(self._read_loop())
        logger.info("self-bot متصل شد: %s", self.url)

    async def close(self) -> None:
        self._closed = True
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reader_task = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._fail_pending(NotConnected("اتصال بسته شد"))

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._closed

    def _fail_pending(self, exc: Exception) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()

    # ---------- خواندن ----------
    async def _read_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                if isinstance(raw, str):
                    raw = raw.encode("utf-8")
                self.stats["received"] += 1
                self._buf += raw
                try:
                    frames, self._buf = self._unframe(self._buf)
                except TransportError:
                    self.stats["errors"] += 1
                    self._buf = b""
                    continue
                for frame in frames:
                    await self._dispatch(frame)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("خواننده قطع شد: %s", exc)
            self.stats["errors"] += 1
        finally:
            if not self._closed:
                await self._handle_drop()

    async def _dispatch(self, frame: bytes) -> None:
        """تحویل قاب به Future مربوطه یا به callback به‌روزرسانی."""
        req_id = _peek_req_id(frame)
        if req_id and req_id in self._pending:
            fut = self._pending.pop(req_id)
            if not fut.done():
                fut.set_result(frame)
            return
        if self.on_update is not None:
            try:
                await self.on_update(frame)
            except Exception as exc:
                logger.warning("callback به‌روزرسانی خطا داد: %s", exc)

    async def _handle_drop(self) -> None:
        """اتصال مجدد با backoff نمایی."""
        self._fail_pending(NotConnected("اتصال قطع شد"))
        if self.on_disconnect is not None:
            try:
                await self.on_disconnect()
            except Exception:
                pass
        delay = 1.0
        for attempt in range(1, self.max_reconnect + 1):
            if self._closed:
                return
            await asyncio.sleep(delay)
            try:
                await self.connect()
                self.stats["reconnects"] += 1
                logger.info("اتصال مجدد موفق (تلاش %d)", attempt)
                return
            except Exception as exc:
                logger.warning("اتصال مجدد %d شکست خورد: %s", attempt, exc)
                delay = min(delay * 2, 30.0)
        logger.error("اتصال مجدد ناموفق؛ تسلیم شد")

    # ---------- نوشتن ----------
    def next_req_id(self) -> str:
        self._seq += 1
        return f"{self._seq:x}"

    async def request(
        self,
        payload: bytes,
        req_id: str | None = None,
        timeout: float | None = None,
    ) -> bytes:
        """ارسال یک درخواست و انتظار پاسخ."""
        if not self.connected:
            raise NotConnected("سوکت باز نیست؛ اول connect() صدا بزن")
        req_id = req_id or self.next_req_id()
        timeout = self.timeout if timeout is None else timeout

        wait = self.rate.wait_needed()
        if wait > 0:
            await asyncio.sleep(wait)

        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut
        body = _stamp_req_id(payload, req_id)
        try:
            async with self._lock:
                assert self._ws is not None
                await self._ws.send(self._frame(body))
                self.rate.note_sent()
                self.stats["sent"] += 1
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise RpcTimeout(f"پاسخ در {timeout} ثانیه نرسید (req_id={req_id})")
        except Exception:
            self._pending.pop(req_id, None)
            raise

    async def send_fire_and_forget(self, payload: bytes) -> None:
        """ارسال بدون انتظار پاسخ (برای update ها)."""
        if not self.connected:
            raise NotConnected("سوکت باز نیست")
        async with self._lock:
            assert self._ws is not None
            await self._ws.send(self._frame(payload))
            self.rate.note_sent()
            self.stats["sent"] += 1


# ---------- شناسه درخواست ----------
# بله شناسه را به‌عنوان یک فیلد varint در پیام می‌فرستد. چون .proto نداریم،
# شناسه را در فیلد 1 به‌عنوان varint می‌گذاریم و در پاسخ هم از همان می‌خوانیم.
# اگر پروتکل عوض شد، این دو تابع تنها نقطه تغییر هستند.
REQ_ID_FIELD = 1


def _stamp_req_id(payload: bytes, req_id: str) -> bytes:
    """افزودن شناسه درخواست به ابتدای پیام."""
    from .proto import enc_varint

    try:
        numeric = int(req_id, 16)
    except ValueError:
        numeric = abs(hash(req_id)) % (1 << 31)
    return enc_varint(REQ_ID_FIELD, numeric) + payload


def _peek_req_id(frame: bytes) -> str | None:
    """خواندن شناسه درخواست از ابتدای پاسخ."""
    from .proto import ProtoError, read_varint

    try:
        key, pos = read_varint(frame, 0)
    except ProtoError:
        return None
    if key >> 3 != REQ_ID_FIELD or (key & 0x07) != 0:
        return None
    try:
        value, _ = read_varint(frame, pos)
    except ProtoError:
        return None
    return f"{value:x}"
