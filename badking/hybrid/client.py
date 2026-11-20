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
    make_chat,
    make_document_content,
    make_text_content,
    PEER_TYPE,
    RpcRegistry,
    decode_response,
    encode_request,
    make_peer,
    registry as default_registry,
)
from .session import Session, SessionStore
from .transport import NotConnected, RpcFailed, RpcTimeout, Transport
from ..utils import extract_join_token

logger = logging.getLogger("badking.hybrid.client")


class SelfBotError(Exception):
    """خطای سطح کلاینت."""


def _as_text(value: Any) -> str:
    """bytes/str/dict → str. فیلدهای رشته‌ای protobuf به‌صورت bytes برمی‌گردند."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, dict):
        inner = value.get("value", "")
        return _as_text(inner) if inner is not None else ""
    if value is None:
        return ""
    return str(value)


def _peer_type_name(num: int) -> str:
    """شماره نوع peer → نام."""
    return {1: "user", 2: "chat", 3: "group", 4: "channel"}.get(int(num), "chat")


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
        transport_factory: Callable[[], Transport] | None = None,
    ):
        self.ws_url = ws_url
        self.registry = registry or default_registry
        self.auto_reconnect = auto_reconnect
        self.timeout = timeout
        self.framing = framing
        self.transport_factory = transport_factory
        self._phone = phone
        self._store: SessionStore | None = None
        self._session: Session | None = None
        self._transport: Transport | None = None
        self._handlers: list[tuple[Callable[[Message], bool], Callable]] = []
        self._raw_handlers: list[Callable] = []
        self._me: Peer | None = None
        self._my_id: int = int(getattr(self._session, "user_id", 0) or 0)
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
        make_transport = self.transport_factory or (
            lambda: Transport(
                self.ws_url,
                headers=self._auth_headers(self._session),
                framing=self.framing,
                timeout=self.timeout,
                max_reconnect=5 if self.auto_reconnect else 0,
            )
        )
        self._transport = make_transport()
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

    async def raw_call(
        self,
        full_name: str,
        fields: dict[int, Any],
        service: str | None = None,
    ) -> dict[int, list[Any]]:
        """صدا زدن RPC با شماره فیلد خام، بدون نیاز به اسکیما.

        این همان دری است که aiobale ندارد: اگر بله متد جدیدی اضافه کند
        و در رجیستری ما نباشد، بدون آپدیت کتابخانه می‌توانی صدایش بزنی.

            # متد فرضی جدید
            await bot.raw_call("messaging.NewThing", {1: peer_bytes, 2: 5})
        """
        if self._transport is None:
            raise NotConnected("اول connect() صدا بزن")

        from .proto import build

        payload = build(fields)
        frame = await self._transport.request(payload, timeout=self.timeout)
        from .proto import decode as _decode

        return _decode(frame)

    async def probe(self, full_name: str) -> dict[str, Any]:
        """بررسی وجود یک RPC روی سرور.

        payload خالی می‌فرستد و خطای سرور را برمی‌گرداند. اگر متد وجود
        داشته باشد، خطای «فیلد لازم» می‌دهد؛ اگر نداشته باشد،
        «unimplemented». برای کشف متدهای مستندنشده.
        """
        if self._transport is None:
            raise NotConnected("اول connect() صدا بزن")

        service, _, method = full_name.rpartition(".")
        try:
            frame = await self._transport.request(b"", timeout=self.timeout)
            return {"exists": True, "raw_len": len(frame)}
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            exists = not any(
                k in msg for k in ("unimplemented", "unknown method", "not found")
            )
            return {"exists": exists, "error": str(exc)}

    def describe(self, full_name: str) -> dict[str, Any]:
        """اسکیمای یک متد: فیلدها، شماره‌ها، پاسخ، و هشدار خطر."""
        spec = self.registry.get(full_name)
        return {
            "name": spec.full_name,
            "service": spec.full_service,
            "doc": spec.doc,
            "dangerous": spec.dangerous,
            "needs_peer": spec.needs_peer,
            "request": spec.schema(),
            "response": spec.resp,
        }

    def search(self, term: str) -> list[str]:
        """جستجوی متد با کلمه کلیدی."""
        return self.registry.search(term)

    # ---------- حساب ----------
    async def get_me(self) -> Peer:
        """اطلاعات اکانت خودمان.

        پروتکل بله users.GetMe ندارد؛ از user.LoadUsers با آیدی خودمان
        استفاده می‌کنیم. آیدی از session می‌آید.
        """
        if self._me is not None:
            return self._me

        my_id = int(self._my_id or 0)
        if not my_id:
            # بدون آیدی نمی‌توان LoadUsers زد؛ از contacts استفاده می‌کنیم
            self._me = Peer(id=0, type="user")
            return self._me

        resp = await self.call(
            "user.LoadUsers", peers=[{"id": my_id, "type": 1}]
        )
        rows = resp.get("data") or []
        if not isinstance(rows, list):
            rows = [rows]
        user = rows[0] if rows and isinstance(rows[0], dict) else {}

        username = _as_text(user.get("username"))

        self._me = Peer(
            id=int(user.get("id", my_id) or my_id),
            type="user",
            title=_as_text(user.get("name")),
            username=str(username or ""),
            access_hash=int(user.get("accessHash", 0) or 0),
        )
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
        """تبدیل یوزرنیم/آیدی/Peer به Peer.

        پروتکل بله ResolveUsername ندارد. برای یوزرنیم از SearchContacts
        استفاده می‌کنیم، و اگر پیدا نشد Peer با آیدی صفر برمی‌گردانیم تا
        فراخواننده خودش تصمیم بگیرد.
        """
        if isinstance(ref, Peer):
            return ref

        key = str(ref)
        if key in self._peer_cache:
            return self._peer_cache[key]

        if isinstance(ref, int) or (isinstance(ref, str) and ref.lstrip("-").isdigit()):
            peer = Peer(id=int(ref), type="chat")
            self._peer_cache[key] = peer
            return peer

        username = key.lstrip("@")

        # تلاش با SearchContacts
        try:
            resp = await self.call("user.SearchContacts", request=username)
            rows = resp.get("peers") or resp.get("data") or []
            if not isinstance(rows, list):
                rows = [rows]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                uname = row.get("username")
                if isinstance(uname, dict):
                    uname = uname.get("value", "")
                if str(uname or "").lstrip("@").lower() == username.lower():
                    peer = Peer(
                        id=int(row.get("id", 0) or 0),
                        type="user",
                        username=username,
                        access_hash=int(row.get("accessHash", 0) or 0),
                    )
                    self._peer_cache[key] = peer
                    return peer
        except Exception as exc:  # noqa: BLE001
            logger.debug("SearchContacts شکست خورد: %s", exc)

        # یوزرنیم کانال/گروه: با آیدی صفر و نام یوزرنیم
        peer = Peer(id=0, type="channel", username=username)
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
        """ارسال پیام متنی از اکانت شخصی.

        ساختار واقعی پروتکل:
            SendMessage{1: Peer, 2: message_id, 3: MessageContent, 5: reply_to, 6: Chat}
            MessageContent{15: TextMessage{1: value}}
        """
        peer = await self.get_entity(ref)
        rid = int(time.time() * 1000)
        resp = await self.call(
            "messaging.SendMessage",
            peer=peer.to_dict(),
            message_id=rid,
            content=make_text_content(text),
            reply_to=(
                {"peer": peer.to_dict(), "messageId": reply_to, "date": int(time.time())}
                if reply_to
                else None
            ),
            chat=make_chat(peer.type, peer.id),
        )
        return Message(
            id=int(resp.get("message_id", rid) or rid),
            text=text,
            chat_id=peer.id,
            date=float(resp.get("date", time.time()) or time.time()),
            peer=peer,
            is_out=True,
            raw=resp,
            _client=self,
        )

    async def send_file(
        self,
        ref: str | int | Peer,
        path: str,
        caption: str | None = None,
    ) -> Message:
        """آپلود و ارسال فایل از اکانت شخصی.

        سه مرحله: گرفتن URL آپلود، آپلود، ارسال با DocumentMessage.
        """
        import os

        peer = await self.get_entity(ref)
        size = os.path.getsize(path)
        name = os.path.basename(path)

        up = await self.call(
            "files.GetNasimFileUploadUrl",
            expected_size=size,
            name=name,
            mime_type="application/octet-stream",
            chat=make_chat(peer.type, peer.id),
            send_type={"type": 1},
        )
        file_id = int(up.get("file_id", 0) or 0)
        access_hash = int(up.get("access_hash", 0) or 0)
        upload_url = up.get("url") or ""

        if upload_url:
            await self._upload_bytes(upload_url, path)

        rid = int(time.time() * 1000)
        resp = await self.call(
            "messaging.SendMessage",
            peer=peer.to_dict(),
            message_id=rid,
            content=make_document_content(
                file_id, access_hash, name=name, size=size, caption=caption
            ),
            chat=make_chat(peer.type, peer.id),
        )
        return Message(
            id=int(resp.get("message_id", rid) or rid),
            text=caption or "",
            chat_id=peer.id,
            date=float(resp.get("date", time.time()) or time.time()),
            peer=peer,
            is_out=True,
            raw=resp,
            _client=self,
        )

    async def _upload_bytes(self, url: str, path: str) -> None:
        """آپلود فایل به URL داده‌شده."""
        try:
            import httpx
        except ImportError:  # pragma: no cover
            logger.warning("httpx نصب نیست؛ آپلود انجام نشد")
            return
        async with httpx.AsyncClient(timeout=120) as client:
            with open(path, "rb") as fh:
                await client.post(url, content=fh.read())

    async def edit_message(
        self, ref: str | int | Peer, message_id: int, text: str
    ) -> bool:
        """ویرایش پیام — RPC واقعی UpdateMessage است، نه EditMessage."""
        peer = await self.get_entity(ref)
        resp = await self.call(
            "messaging.UpdateMessage",
            peer=peer.to_dict(),
            message_id=message_id,
            updated_message=make_text_content(text),
        )
        return bool(resp.get("message_id") or resp.get("date"))

    async def delete_messages(
        self, ref: str | int | Peer, message_ids: list[int], revoke: bool = True
    ) -> bool:
        """حذف پیام."""
        peer = await self.get_entity(ref)
        resp = await self.call(
            "messaging.DeleteMessage",
            peer=peer.to_dict(),
            message_ids=message_ids,
            just_me={"value": not revoke},
        )
        return bool(resp) or True

    async def forward_messages(
        self,
        to: str | int | Peer,
        message_ids: list[int],
        from_peer: str | int | Peer,
    ) -> bool:
        """فوروارد — RPC واقعی ForwardMessages (جمع) است."""
        target = await self.get_entity(to)
        source = await self.get_entity(from_peer)
        await self.call(
            "messaging.ForwardMessages",
            peer=source.to_dict(),
            message_ids=message_ids,
            forwarded_messages=[
                {"peer": target.to_dict(), "messageId": m} for m in message_ids
            ],
        )
        return True

    async def react(self, ref: str | int | Peer, message_id: int, code: str) -> bool:
        """گذاشتن واکنش — سرویس ABACUS، نه reactions."""
        peer = await self.get_entity(ref)
        await self.call(
            "abacus.MessageSetReaction",
            peer=peer.to_dict(),
            message_id=message_id,
            emojy=code,
            date=int(time.time()),
        )
        return True

    async def remove_reaction(
        self, ref: str | int | Peer, message_id: int, code: str
    ) -> bool:
        """برداشتن واکنش."""
        peer = await self.get_entity(ref)
        await self.call(
            "abacus.MessageRemoveReaction",
            peer=peer.to_dict(),
            message_id=message_id,
            emojy=code,
            date=int(time.time()),
        )
        return True

    async def get_reactions(self, ref: str | int | Peer, message_id: int) -> dict:
        """واکنش‌های یک پیام."""
        peer = await self.get_entity(ref)
        return await self.call(
            "abacus.GetMessagesReactions",
            peer=peer.to_dict(),
            message_ids=[{"messageId": message_id}],
        )

    async def get_views(self, ref: str | int | Peer, message_ids: list[int]) -> dict:
        """تعداد بازدید پیام‌ها."""
        peer = await self.get_entity(ref)
        return await self.call(
            "abacus.GetMessagesViews",
            peer=peer.to_dict(),
            message_ids=[{"messageId": m} for m in message_ids],
        )

    async def mark_read(self, ref: str | int | Peer) -> bool:
        """علامت‌گذاری خوانده‌شده."""
        peer = await self.get_entity(ref)
        await self.call(
            "messaging.MessageRead", peer=peer.to_dict(), date=int(time.time())
        )
        return True

    async def send_typing(self, ref: str | int | Peer) -> bool:
        """شروع تایپ — سرویس PRESENCE، نه messaging."""
        peer = await self.get_entity(ref)
        await self.call("presence.Typing", peer=peer.to_dict(), typing_type=1)
        return True

    async def stop_typing(self, ref: str | int | Peer) -> bool:
        """توقف تایپ."""
        peer = await self.get_entity(ref)
        await self.call("presence.StopTyping", peer=peer.to_dict())
        return True

    async def set_online(self) -> bool:
        """اعلام آنلاین بودن."""
        await self.call("presence.SetOnline", is_online=True)
        return True

    async def pin_message(self, ref: str | int | Peer, message_id: int) -> bool:
        """سنجاق پیام."""
        peer = await self.get_entity(ref)
        await self.call(
            "messaging.PinMessage",
            peer=peer.to_dict(),
            message={"messageId": message_id},
        )
        return True

    async def unpin_message(self, ref: str | int | Peer, message_id: int) -> bool:
        """برداشتن سنجاق."""
        peer = await self.get_entity(ref)
        await self.call(
            "messaging.UnPinMessages",
            peer=peer.to_dict(),
            messages=[{"messageId": message_id}],
        )
        return True

    async def get_pinned(self, ref: str | int | Peer) -> list[Message]:
        """پیام‌های سنجاق‌شده."""
        peer = await self.get_entity(ref)
        resp = await self.call("messaging.LoadPinnedMessages", peer=peer.to_dict())
        rows = resp.get("pins_data") or resp.get("pinsData") or []
        if not isinstance(rows, list):
            rows = [rows]
        return [self._parse_message(r, peer) for r in rows]

    async def clear_history(self, ref: str | int | Peer) -> bool:
        """پاک کردن تاریخچه چت."""
        peer = await self.get_entity(ref)
        await self.call("messaging.ClearChat", peer=peer.to_dict())
        return True

    # ---------- گروه و کانال ----------
    async def create_group(
        self,
        title: str,
        users: list[dict] | None = None,
        channel: bool = False,
        username: str | None = None,
    ) -> dict:
        """ساخت گروه یا کانال."""
        import random

        return await self.call(
            "groups.CreateGroup",
            random_id=random.randint(1, 2**62),
            title=title,
            users=users or [],
            group_type=1 if channel else 0,
            username={"value": username} if username else None,
            restriction=0,
        )

    async def get_group(self, ref: str | int | Peer) -> dict:
        """اطلاعات کامل گروه."""
        peer = await self.get_entity(ref)
        return await self.call("groups.GetFullGroup", peer=peer.to_dict())

    async def join_group(self, token: str) -> dict:
        """ورود به گروه با لینک دعوت."""
        return await self.call("groups.JoinGroup", token=token)

    async def leave_group(self, ref: str | int | Peer) -> bool:
        """ترک گروه."""
        peer = await self.get_entity(ref)
        await self.call("groups.LeaveGroup", peer=peer.to_dict())
        return True

    async def invite_users(
        self, ref: str | int | Peer, user_ids: list[int]
    ) -> dict:
        """دعوت کاربران به گروه."""
        peer = await self.get_entity(ref)
        return await self.call(
            "groups.InviteUsers",
            peer=peer.to_dict(),
            users=[{"id": u, "accessHash": 0} for u in user_ids],
        )

    async def kick_user(self, ref: str | int | Peer, user_id: int) -> bool:
        """اخراج کاربر."""
        peer = await self.get_entity(ref)
        await self.call(
            "groups.KickUser", peer=peer.to_dict(), user_id=user_id
        )
        return True

    async def get_members(self, ref: str | int | Peer, limit: int = 100) -> dict:
        """لیست اعضای گروه."""
        peer = await self.get_entity(ref)
        return await self.call(
            "groups.LoadMembers", peer=peer.to_dict(), limit=limit
        )

    async def get_invite_link(self, ref: str | int | Peer) -> str:
        """ساخت لینک دعوت."""
        peer = await self.get_entity(ref)
        resp = await self.call("groups.GetGroupInviteURL", peer=peer.to_dict())
        return str(resp.get("url", "") or "")

    # ---------- مخاطبین ----------
    async def get_contacts(self) -> dict:
        """لیست مخاطبین."""
        return await self.call("user.GetContacts")

    async def add_contact(self, phone: str, name: str) -> dict:
        """افزودن مخاطب."""
        return await self.call(
            "user.AddContact",
            request={"phoneNumber": int(phone), "name": {"value": name}},
        )

    async def block_user(self, user_id: int) -> bool:
        """مسدود کردن کاربر."""
        await self.call("user.BlockUser", user_id=user_id)
        return True

    async def unblock_user(self, user_id: int) -> bool:
        """رفع مسدودی."""
        await self.call("user.UnblockUser", user_id=user_id)
        return True

    # ---------- پروفایل ----------
    async def edit_name(self, name: str) -> bool:
        """تغییر نام پروفایل."""
        await self.call("user.EditName", name=name)
        return True

    async def edit_about(self, about: str) -> bool:
        """تغییر بیو."""
        await self.call("user.EditAbout", about=about)
        return True

    async def check_username(self, username: str) -> bool:
        """بررسی آزاد بودن یوزرنیم."""
        resp = await self.call("user.CheckNickName", nickname=username)
        return bool(resp.get("available"))

    # ---------- تاریخچه و گفتگوها ----------
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

        LoadHistory{1: peer, 2: date, 3: loadMode, 4: limit}
        loadMode: 1=forward, 2=backward, 3=both
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
                offset_date=date_cursor,
                load_mode=2,
                limit=want,
            )
            raw_messages = resp.get("data") or resp.get("messages") or []
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

            # ادامه تا وقتی پیام تازه بیاید؛ اگر صفحه خالی یا بدون
            # پیشرفت در تاریخ بود، تمام است.
            oldest = min((m.date for m in page), default=None)
            if oldest is None or int(oldest) == int(date_cursor):
                return
            date_cursor = int(oldest)

    def _parse_message(self, raw: Any, peer: Peer) -> Message:
        """تبدیل MessageData خام به Message.

        MessageData{1: senderId, 2: messageId, 3: date, 4: content, 12: editedAt}
        content = MessageContent{15: TextMessage{1: value}}
        """
        if not isinstance(raw, dict):
            return Message(id=0, peer=peer, _client=self)

        text = ""
        content = raw.get("content")
        if isinstance(content, dict):
            text_node = content.get("text")
            if isinstance(text_node, dict):
                text = str(text_node.get("value", "") or "")
            elif isinstance(text_node, bytes):
                text = text_node.decode("utf-8", "replace")
            elif isinstance(text_node, str):
                text = text_node

        return Message(
            id=int(raw.get("messageId", 0) or 0),
            text=text,
            sender_id=int(raw.get("senderId", 0) or 0),
            chat_id=peer.id,
            date=float(raw.get("date", 0) or 0),
            peer=peer,
            is_out=int(raw.get("senderId", 0) or 0) == int(self._my_id or 0),
            raw=raw,
            _client=self,
        )

    # ---------- گفتگوها ----------
    async def get_dialogs(self, limit: int = 100) -> list[Dialog]:
        return [d async for d in self.iter_dialogs(limit=limit)]

    async def iter_dialogs(
        self, limit: int | None = None, batch: int = 50
    ) -> AsyncIterator[Dialog]:
        """پیمایش گفتگوها.

        LoadDialogs{1: limit, 2: offset} → {3: [PeerData]}
        """
        offset = 0
        fetched = 0
        while True:
            want = batch if limit is None else min(batch, limit - fetched)
            if want <= 0:
                return
            resp = await self.call(
                "messaging.LoadDialogs", limit=want, offset_date=offset
            )
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
            if len(rows) < want:
                return
            offset += len(rows)

    def _parse_dialog(self, raw: Any) -> Dialog:
        """تبدیل PeerData به Dialog.

        PeerData{1: peer, 2: unreadCount, 3: sortDate, 6: date, 7: content}
        """
        if not isinstance(raw, dict):
            return Dialog(peer=Peer(id=0))

        peer_raw = raw.get("peer") or {}
        ptype = int(peer_raw.get("type", 2) or 2) if isinstance(peer_raw, dict) else 2
        peer = Peer(
            id=int(peer_raw.get("id", 0) or 0) if isinstance(peer_raw, dict) else 0,
            type=_peer_type_name(ptype),
            access_hash=(
                int(peer_raw.get("accessHash", 0) or 0)
                if isinstance(peer_raw, dict)
                else 0
            ),
        )

        last_text = ""
        content = raw.get("content")
        if isinstance(content, dict):
            node = content.get("text")
            if isinstance(node, dict):
                last_text = str(node.get("value", "") or "")

        return Dialog(
            peer=peer,
            unread=int(raw.get("unreadCount", 0) or 0),
            last_message=last_text,
            last_date=float(raw.get("date", 0) or 0),
            pinned=False,
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

    # ---------- کیف پول ----------
    async def get_wallet(self) -> dict[str, Any]:
        """موجودی کیف پول اکانت.

        پروتکل بله کیف پول را در سرویس ABACUS دارد (GetMyKifpools)،
        نه wallet.GetWallet. این متد نام درست را صدا میزند و نتیجه را
        ساده میکند تا ``balance`` همیشه سرراست باشد.
        """
        resp = await self.call("abacus.GetMyKifpools")
        wallet = resp.get("wallet") or {}
        if not isinstance(wallet, dict):
            wallet = {}
        return {
            "balance": int(wallet.get("balance", 0) or 0),
            "is_merchant": bool(wallet.get("isMerchant", 0)),
            "level": wallet.get("level", 0),
            "raw": resp,
        }

    def wallet_balance(self, resp: dict[str, Any] | None = None) -> int:
        """گرفتن موجودی از نتیجه get_wallet (یا صدا زدن دوباره).

        این همان کاری است که main-3.py با ``wallet.wallet.balance // 10``
        میکرد، ولی بدون وابستگی به ساختار شیء.
        """
        if resp is None:
            raise ValueError("نتیجه get_wallet را بده")
        return int(resp.get("balance", 0) or 0)

    async def get_full_me(self) -> dict[str, Any]:
        """اطلاعات کامل اکانت: آیدی، نام، شماره، یوزرنیم.

        جایگزین ``client.get_full_me()`` در aiobale.
        """
        me = await self.get_me()
        phone = self._session.phone if self._session else ""
        return {
            "id": me.id,
            "name": me.title,
            "username": me.username,
            "phone": phone,
            "peer": me.to_dict(),
        }

    async def get_group_preview(self, link: str) -> dict[str, Any]:
        """پیشنمایش گروه از روی لینک دعوت.

        جایگزین ``client.get_group_preview()`` در aiobale.
        ``is_joined`` و ``id`` و ``title`` را برمیگرداند.
        """
        token = extract_join_token(link)
        if not token:
            raise SelfBotError(f"لینک دعوت معتبر نیست: {link!r}")
        resp = await self.call("groups.GetGroupPreview", token=token)
        group = resp.get("group") or resp
        if not isinstance(group, dict):
            group = {}
        return {
            "id": int(group.get("id", 0) or 0),
            "title": str(group.get("title", "") or ""),
            "is_joined": bool(group.get("isJoined", 0) or resp.get("isJoined", 0)),
            "raw": resp,
        }

    async def join_by_link(self, link: str) -> dict[str, Any]:
        """ورود به گروه با لینک (همراه استخراج توکن)."""
        token = extract_join_token(link)
        if not token:
            raise SelfBotError(f"لینک دعوت معتبر نیست: {link!r}")
        return await self.call("groups.JoinGroup", token=token)

    async def leave_by_id(self, group_id: int) -> bool:
        """ترک گروه با آیدی عددی (همان کاری که main-3.py با id+2^32 میکرد)."""
        await self.call(
            "groups.LeaveGroup",
            group={"id": int(group_id), "type": 4},
            random_id=int(time.time()),
        )
        return True

    async def report_chat(
        self,
        chat_id: int,
        chat_type: int = 3,
        reason: str = "محتوای نامناسب",
    ) -> bool:
        """گزارش یک چت.

        Args:
            chat_id: آیدی عددی چت.
            chat_type: ۱=خصوصی، ۲=کانال، ۳=گروه.
            reason: متن دلیل گزارش.
        """
        await self.call(
            "report.ReportInappropriateContent",
            report_body={
                "peer": {"id": int(chat_id), "type": int(chat_type)},
                "messages": [],
                "kind": str(reason),
            },
        )
        return True

    async def set_reaction(
        self, ref: str | int | Peer, message_id: int, emoji: str
    ) -> bool:
        """گذاشتن واکنش (نام مستعار واضحتر react)."""
        return await self.react(ref, message_id, emoji)

    async def upvote(self, ref: str | int | Peer, message_id: int) -> bool:
        """لایک پست مجله."""
        peer = await self.get_entity(ref)
        await self.call(
            "magazine.UpvotePost",
            message={"peer": peer.to_dict(), "messageId": int(message_id)},
            album_id={"value": 0},
        )
        return True

    # ---------- آمار ----------
    def stats(self) -> dict[str, Any]:
        if self._transport is None:
            return {"connected": False}
        return {"connected": self.connected, **self._transport.stats}
