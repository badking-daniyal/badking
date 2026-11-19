"""کلاینت self-bot: API سطح‌بالا روی transport + RPC.

این همان چیزی است که کاربر با آن کار می‌کند:

    async with SelfBot(session="me.session") as bot:
        me = await bot.get_me()
        await bot.send_message("@channel", "سلام")
        async for msg in bot.iter_messages("@channel", limit=100):
            print(msg.text)

هشدار: غیررسمی. ریسک مسدود شدن اکانت.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from .auth import DEFAULT_WS_URL, AuthFlow, AuthError, interactive_login, normalize_phone
from .proto import decode, get_int, get_str
from .rpc import (
    PEER_TYPE,
    RpcRegistry,
    decode_response,
    encode_request,
    make_peer,
    registry as default_registry,
)
from .session import Session, SessionStore
from .transport import NotConnected, RpcFailed, RpcTimeout, Transport

logger = logging.getLogger("badking.hybrid.client")


class SelfBotError(Exception):
    """خطای سطح کلاینت."""


@dataclass
class Peer:
    """یک گفتگو/کاربر/کانال."""

    id: int
    type: str = "user"
    access_hash: int = 0
    title: str = ""
    username: str = ""

    def to_dict(self) -> dict[str, Any]:
        """ساختار peer برای ارسال. کلیدها همان نام فیلدهای اسکیما هستند."""
        return {"type": PEER_TYPE[self.type], "id": self.id, "accessHash": self.access_hash}

    def __str__(self) -> str:
        return self.username or self.title or str(self.id)


@dataclass
class Message:
    """یک پیام دریافتی یا ارسالی."""

    id: int
    text: str = ""
    sender_id: int = 0
    chat_id: int = 0
    date: float = 0.0
    peer: Peer | None = None
    is_out: bool = False
    raw: dict[str, Any] = field(default_factory=dict)
    _client: Any = None

    async def reply(self, text: str) -> "Message":
        if self._client is None or self.peer is None:
            raise SelfBotError("این پیام به کلاینت وصل نیست")
        return await self._client.send_message(self.peer, text, reply_to=self.id)

    async def delete(self, revoke: bool = True) -> bool:
        if self._client is None or self.peer is None:
            raise SelfBotError("این پیام به کلاینت وصل نیست")
        return await self._client.delete_messages(self.peer, [self.id], revoke=revoke)

    async def react(self, code: str) -> bool:
        if self._client is None or self.peer is None:
            raise SelfBotError("این پیام به کلاینت وصل نیست")
        return await self._client.react(self.peer, self.id, code)

    async def mark_read(self) -> bool:
        if self._client is None or self.peer is None:
            raise SelfBotError("این پیام به کلاینت وصل نیست")
        return await self._client.mark_read(self.peer)


@dataclass
class Dialog:
    """یک ردیف در لیست گفتگوها."""

    peer: Peer
    unread: int = 0
    last_message: str = ""
    last_date: float = 0.0
    pinned: bool = False

    @property
    def title(self) -> str:
        return self.peer.title or self.peer.username or str(self.peer.id)


class SelfBot:
    """کلاینت self-bot بله.

    Args:
        session: مسیر فایل session، یا یک Session آماده، یا None.
        phone: اگر session نداری، شماره برای ورود تعاملی.
        password: رمز فایل session.
        ws_url: آدرس WebSocket (قابل override).
        registry: رجیستری RPC سفارشی.
        auto_reconnect: اتصال مجدد خودکار.
    """

    def __init__(
        self,
        session: str | Path | Session | None = None,
        phone: str | None = None,
        password: str | None = None,
        ws_url: str = DEFAULT_WS_URL,
        registry: RpcRegistry | None = None,
        auto_reconnect: bool = True,
        timeout: float = 30.0,
        framing: str = "length",
    ):
        self.ws_url = ws_url
        self.registry = registry or default_registry
        self.auto_reconnect = auto_reconnect
        self.timeout = timeout
        self.framing = framing
        self._phone = phone
        self._store: SessionStore | None = None
        self._session: Session | None = None
        self._transport: Transport | None = None
        self._handlers: list[tuple[Callable[[Message], bool], Callable]] = []
        self._raw_handlers: list[Callable] = []
        self._me: Peer | None = None
        self._peer_cache: dict[str, Peer] = {}

        if isinstance(session, Session):
            self._session = session
        elif session is not None:
            self._store = SessionStore(session, password=password)
            self._session = self._store.get()
        elif password is not None:
            self._store = SessionStore("badking.session", password=password)
            self._session = self._store.get()

    # ---------- چرخه حیات ----------
    async def connect(self) -> "SelfBot":
        """باز کردن اتصال. اگر session نداری، ورود تعاملی."""
        if self._session is None or not self._session.is_valid():
            if not self._phone:
                raise SelfBotError(
                    "session معتبر نداری. یا phone بده، یا اول با "
                    "`badking login` وارد شو."
                )
            await self._do_login()

        assert self._session is not None
        self._transport = Transport(
            self.ws_url,
            headers=self._auth_headers(self._session),
            framing=self.framing,
            timeout=self.timeout,
            max_reconnect=5 if self.auto_reconnect else 0,
        )
        self._transport.on_update = self._on_raw_update
        await self._transport.connect()
        return self

    def _auth_headers(self, session: Session) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {session.access_token}",
            "User-Agent": "BADKING/1.0",
            "Origin": "https://web.bale.ai",
        }

    async def _do_login(self) -> None:
        """ورود تعاملی با شماره و کد."""
        assert self._phone is not None
        self._store = self._store or SessionStore("badking.session")

        async def factory() -> Transport:
            t = Transport(self.ws_url, framing=self.framing, timeout=self.timeout)
            await t.connect()
            return t

        # ورود روی یک transport موقت انجام می‌شود
        transport = Transport(self.ws_url, framing=self.framing, timeout=self.timeout)
        await transport.connect()
        try:
            flow = AuthFlow(transport)
            req = await flow.request_code(self._phone)
            code = await asyncio.get_event_loop().run_in_executor(
                None, input, "کد تأیید SMS: "
            )
            result = await flow.sign_in(req.transaction_hash, code, phone=req.phone)
            self._session = result.session
            self._store.put(result.session)
        finally:
            await transport.close()

    async def close(self) -> None:
        if self._transport is not None:
            await self._transport.close()
            self._transport = None

    async def __aenter__(self) -> "SelfBot":
        return await self.connect()

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    @property
    def connected(self) -> bool:
        return self._transport is not None and self._transport.connected

    @property
    def session(self) -> Session | None:
        return self._session

    # ---------- فراخوانی خام ----------
    async def call(self, full_name: str, **kwargs: Any) -> dict[str, Any]:
        """فراخوانی هر RPC با نام کامل و آرگومان نام‌دار.

        این درِ خروج Layer 2 است: هر چیزی که در رجیستری باشد، یا خودت
        اضافه کنی، از همین‌جا صدا زده می‌شود.
        """
        if self._transport is None:
            raise NotConnected("اول connect() صدا بزن")
        spec = self.registry.get(full_name)
        payload = encode_request(spec, kwargs)
        frame = await self._transport.request(payload, timeout=self.timeout)
        return decode_response(spec, frame)

    # ---------- حساب ----------
    async def get_me(self) -> Peer:
        if self._me is not None:
            return self._me
        resp = await self.call("users.GetMe")
        user = resp.get("user") or {}
        if isinstance(user, dict):
            self._me = Peer(
                id=int(user.get("id", 0) or 0),
                type="user",
                title=str(user.get("name", "") or ""),
                username=str(user.get("username", "") or ""),
            )
        else:
            self._me = Peer(id=0, type="user")
        return self._me

    async def edit_profile(
        self, name: str | None = None, username: str | None = None, about: str | None = None
    ) -> bool:
        resp = await self.call(
            "users.EditProfile", name=name, username=username, about=about
        )
        return bool(resp.get("ok"))

    # ---------- peer ----------
    async def get_entity(self, ref: str | int | Peer) -> Peer:
        """تبدیل یوزرنیم/آیدی/Peer به Peer."""
        if isinstance(ref, Peer):
            return ref
        key = str(ref)
        if key in self._peer_cache:
            return self._peer_cache[key]

        if isinstance(ref, int) or (isinstance(ref, str) and ref.lstrip("-").isdigit()):
            peer = Peer(id=int(ref), type="chat")
        else:
            username = key.lstrip("@")
            resp = await self.call("users.ResolveUsername", username=username)
            raw = resp.get("peer") or {}
            peer = Peer(
                id=int(raw.get("id", 0) or 0) if isinstance(raw, dict) else 0,
                type="channel",
                access_hash=int(raw.get("accessHash", 0) or 0) if isinstance(raw, dict) else 0,
                username=username,
            )
        self._peer_cache[key] = peer
        return peer

    # ---------- پیام ----------
    async def send_message(
        self,
        ref: str | int | Peer,
        text: str,
        reply_to: int | None = None,
        silent: bool = False,
    ) -> Message:
        """ارسال پیام متنی."""
        peer = await self.get_entity(ref)
        rid = int(time.time() * 1000)
        message_body = {"textMessage": {"text": text}}
        resp = await self.call(
            "messaging.SendMessage",
            peer=peer.to_dict(),
            rid=rid,
            message=message_body,
            isSilent=silent,
            replyTo=reply_to,
        )
        return Message(
            id=int(resp.get("rid", rid) or rid),
            text=text,
            chat_id=peer.id,
            date=float(resp.get("date", time.time()) or time.time()),
            peer=peer,
            is_out=True,
            raw=resp,
            _client=self,
        )

    async def edit_message(
        self, ref: str | int | Peer, message_id: int, text: str
    ) -> bool:
        peer = await self.get_entity(ref)
        resp = await self.call(
            "messaging.EditMessage",
            peer=peer.to_dict(),
            rid=message_id,
            message={"textMessage": {"text": text}},
        )
        return bool(resp.get("rid") or resp.get("date"))

    async def delete_messages(
        self, ref: str | int | Peer, message_ids: list[int], revoke: bool = True
    ) -> bool:
        peer = await self.get_entity(ref)
        resp = await self.call(
            "messaging.DeleteMessage",
            peer=peer.to_dict(),
            rids=message_ids,
            revoke=revoke,
        )
        return bool(resp.get("deleted", True))

    async def forward_messages(
        self,
        to: str | int | Peer,
        message_ids: list[int],
        from_peer: str | int | Peer,
    ) -> bool:
        target = await self.get_entity(to)
        source = await self.get_entity(from_peer)
        resp = await self.call(
            "messaging.ForwardMessage",
            to=target.to_dict(),
            **{"from": source.to_dict()},
            rids=message_ids,
        )
        return bool(resp.get("rids"))

    async def react(self, ref: str | int | Peer, message_id: int, code: str) -> bool:
        peer = await self.get_entity(ref)
        resp = await self.call(
            "reactions.AddReaction",
            peer=peer.to_dict(),
            rid=message_id,
            date=int(time.time()),
            code=code,
        )
        return bool(resp.get("ok", True))

    async def mark_read(self, ref: str | int | Peer) -> bool:
        peer = await self.get_entity(ref)
        resp = await self.call(
            "messaging.ReadMessage", peer=peer.to_dict(), date=int(time.time())
        )
        return bool(resp.get("ok", True))

    async def send_typing(self, ref: str | int | Peer) -> bool:
        peer = await self.get_entity(ref)
        resp = await self.call(
            "messaging.SendTyping", peer=peer.to_dict(), typing=True
        )
        return bool(resp.get("ok", True))

    async def get_messages(
        self, ref: str | int | Peer, limit: int = 100
    ) -> list[Message]:
        return [m async for m in self.iter_messages(ref, limit=limit)]

    async def iter_messages(
        self,
        ref: str | int | Peer,
        limit: int | None = None,
        batch: int = 50,
        reverse: bool = False,
    ) -> AsyncIterator[Message]:
        """پیمایش تاریخچه پیام‌ها با صفحه‌بندی خودکار.

        این همان قابلیتی است که aiobale دارد؛ اینجا با حذف تکراری و
        مدیریت خودکار hasMore پیاده شده.
        """
        peer = await self.get_entity(ref)
        seen: set[int] = set()
        fetched = 0
        date_cursor = -1
        while True:
            want = batch if limit is None else min(batch, limit - fetched)
            if want <= 0:
                return
            resp = await self.call(
                "messaging.LoadHistory",
                peer=peer.to_dict(),
                date=date_cursor,
                loadMode=2,
                limit=want,
            )
            raw_messages = resp.get("messages") or []
            if not raw_messages:
                return
            if not isinstance(raw_messages, list):
                raw_messages = [raw_messages]

            page: list[Message] = []
            for raw in raw_messages:
                msg = self._parse_message(raw, peer)
                if msg.id in seen:
                    continue
                seen.add(msg.id)
                page.append(msg)

            if reverse:
                page.reverse()
            for msg in page:
                yield msg
                fetched += 1
                if limit is not None and fetched >= limit:
                    return

            if not resp.get("hasMore"):
                return
            last_date = resp.get("lastDate")
            if last_date is None:
                return
            date_cursor = int(last_date)

    def _parse_message(self, raw: Any, peer: Peer) -> Message:
        if not isinstance(raw, dict):
            return Message(id=0, peer=peer, _client=self)
        text = ""
        body = raw.get("message")
        if isinstance(body, dict):
            text_msg = body.get("textMessage")
            if isinstance(text_msg, dict):
                text = str(text_msg.get("text", "") or "")
            elif isinstance(text_msg, bytes):
                text = text_msg.decode("utf-8", "replace")
        return Message(
            id=int(raw.get("rid", 0) or 0),
            text=text,
            sender_id=int(raw.get("senderId", 0) or 0),
            chat_id=peer.id,
            date=float(raw.get("date", 0) or 0),
            peer=peer,
            is_out=bool(raw.get("isOut")),
            raw=raw,
            _client=self,
        )

    # ---------- گفتگوها ----------
    async def get_dialogs(self, limit: int = 100) -> list[Dialog]:
        return [d async for d in self.iter_dialogs(limit=limit)]

    async def iter_dialogs(self, limit: int | None = None, batch: int = 50) -> AsyncIterator[Dialog]:
        offset = 0
        fetched = 0
        while True:
            want = batch if limit is None else min(batch, limit - fetched)
            if want <= 0:
                return
            resp = await self.call("messaging.LoadDialogs", limit=want, offset=offset)
            rows = resp.get("dialogs") or []
            if not rows:
                return
            if not isinstance(rows, list):
                rows = [rows]
            for row in rows:
                yield self._parse_dialog(row)
                fetched += 1
                if limit is not None and fetched >= limit:
                    return
            if not resp.get("hasMore"):
                return
            offset += len(rows)

    def _parse_dialog(self, raw: Any) -> Dialog:
        if not isinstance(raw, dict):
            return Dialog(peer=Peer(id=0))
        peer_raw = raw.get("peer") or {}
        peer = Peer(
            id=int(peer_raw.get("id", 0) or 0) if isinstance(peer_raw, dict) else 0,
            type="chat",
            access_hash=int(peer_raw.get("accessHash", 0) or 0) if isinstance(peer_raw, dict) else 0,
            title=str(raw.get("title", "") or ""),
        )
        return Dialog(
            peer=peer,
            unread=int(raw.get("unreadCount", 0) or 0),
            last_message=str(raw.get("lastMessage", "") or ""),
            last_date=float(raw.get("lastDate", 0) or 0),
            pinned=bool(raw.get("pinned")),
        )

    # ---------- رویدادها ----------
    def on(
        self,
        predicate: Callable[[Message], bool] | None = None,
    ) -> Callable[[Callable], Callable]:
        """دکوراتور ثبت هندلر پیام.

            @bot.on(lambda m: m.text == "/ping")
            async def ping(msg): await msg.reply("pong")
        """

        def decorator(fn: Callable) -> Callable:
            self._handlers.append((predicate or (lambda m: True), fn))
            return fn

        return decorator

    def on_raw(self, fn: Callable) -> Callable:
        """هندلر روی هر update خام (قبل از تفسیر)."""
        self._raw_handlers.append(fn)
        return fn

    async def _on_raw_update(self, frame: bytes) -> None:
        for fn in self._raw_handlers:
            try:
                result = fn(frame)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.warning("هندلر raw خطا داد: %s", exc)

        msg = self._try_parse_update(frame)
        if msg is None:
            return
        for predicate, fn in self._handlers:
            try:
                if not predicate(msg):
                    continue
                result = fn(msg)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.warning("هندلر پیام خطا داد: %s", exc)

    def _try_parse_update(self, frame: bytes) -> Message | None:
        """تلاش برای تفسیر یک update به Message. اگر نشد None."""
        try:
            raw = decode(frame)
        except Exception:
            return None
        # بدون .proto، هر دیکشنری که rid و message دارد را پیام می‌گیریم
        for values in raw.values():
            for value in values:
                if isinstance(value, dict) and ("rid" in value or "message" in value):
                    return self._parse_message(value, Peer(id=0))
        return None

    async def run_until_disconnected(self) -> None:
        """حلقه بی‌پایان تا قطع اتصال."""
        if self._transport is None:
            raise NotConnected("اول connect() صدا بزن")
        while self.connected:
            await asyncio.sleep(0.25)

    # ---------- کیف پول ----------
    async def get_wallet(self) -> dict[str, Any]:
        return await self.call("wallet.GetWallet")

    async def transfer_money(
        self, to: str | int | Peer, amount: int, description: str = ""
    ) -> dict[str, Any]:
        peer = await self.get_entity(to)
        return await self.call(
            "wallet.TransferMoney",
            to=peer.to_dict(),
            amount=amount,
            description=description,
        )

    # ---------- آمار ----------
    def stats(self) -> dict[str, Any]:
        if self._transport is None:
            return {"connected": False}
        return {"connected": self.connected, **self._transport.stats}
