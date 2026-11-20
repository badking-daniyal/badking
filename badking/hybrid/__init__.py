"""لایه Hybrid — self-bot واقعی روی API داخلی بله.

این لایه **پیش‌فرض خاموش** است و بدون `ack_risk=True` فعال نمی‌شود، چون:
    • از API داخلی غیررسمی بله استفاده می‌کند (ممکن است بشکند)
    • با شماره تلفن لاگین می‌کند، نه توکن رسمی
    • خطر مسدود شدن اکانت شخصی وجود دارد

وقتی فعال شد، این‌ها را دارد:
    • ورود با شماره + کد SMS
    • خواندن تاریخچه کامل پیام‌ها
    • ارسال از اکانت شخصی
    • گروه‌ها، کانال‌ها، مخاطبین، واکنش‌ها، وضعیت آنلاین
    • کیف پول
    • هر RPC داخلی، حتی آن‌هایی که پیاده‌سازی آماده ندارند

معماری:
    session.py    → ذخیره امن اکانت‌ها (چند اکانت، رمزنگاری at-rest)
    proto.py      → کدک protobuf از صفر، بدون .proto
    transport.py  → WebSocket، تطبیق درخواست/پاسخ، اتصال مجدد، یادگیری نرخ
    rpc.py        → رجیستری ۷۹ متد با شماره فیلد قابل override
    auth.py       → جریان شماره + کد SMS
    client.py     → API سطح‌بالا (SelfBot)
"""

from __future__ import annotations

from .auth import (
    AuthError,
    AuthFlow,
    CodeRequest,
    SignInResult,
    device_fingerprint,
    interactive_login,
    normalize_phone,
)
from .client import Dialog, Message, Peer, SelfBot, SelfBotError
from .proto import ProtoError, build, decode, encode_named
from .rpc import (
    CHAT_TYPE,
    MESSAGE_BODY_SCHEMA,
    MESSAGE_CONTENT_SCHEMA,
    PEER_SCHEMA,
    PEER_TYPE,
    RpcRegistry,
    RpcSpec,
    decode_response,
    encode_request,
    make_chat,
    make_document_content,
    make_inline_keyboard,
    make_peer,
    make_text_content,
    registry,
)
from .session import Session, SessionError, SessionStore
from .sessions import (
    AccountInfo,
    CheckReport,
    CreateResult,
    SessionManager,
    SessionManagerError,
)
from .transport import (
    NotConnected,
    RpcFailed,
    RpcTimeout,
    Transport,
    TransportError,
    frame_length_prefixed,
    unframe_length_prefixed,
)


class HybridDisabledError(Exception):
    """سعی در استفاده از self-bot بدون تأیید ریسک."""


HYBRID_WARNING = (
    "HYBRID / SELF-BOT MODE\n"
    "  • از Internal API غیررسمی بله استفاده می‌کند (قابل شکستن).\n"
    "  • نیاز به لاگین شماره تلفن دارد، نه توکن رسمی.\n"
    "  • خطر بسته شدن اکانت شخصی وجود دارد.\n"
    "  • اسرار را فقط در keyring سیستم ذخیره کن.\n"
)


def hybrid_warning() -> str:
    return HYBRID_WARNING


class HybridPlugin:
    """پلاگین self-bot.

    بدون `ack_risk=True` هرگز فعال نمی‌شود. وقتی فعال شد، یک `SelfBot`
    آماده در `.bot` می‌گذارد.

        plugin = HybridPlugin(enabled=True, ack_risk=True, session="me.session")
        await plugin.activate()
        await plugin.bot.send_message("@channel", "سلام")
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        ack_risk: bool = False,
        session: object = None,
        phone: str | None = None,
        password: str | None = None,
        ws_url: str | None = None,
        storage: object = None,
        dispatcher: object = None,
    ):
        self.enabled = enabled and ack_risk
        self.ack_risk = ack_risk
        self.storage = storage
        self.dispatcher = dispatcher
        self._lane_name = "selfbot"
        self._session_arg = session
        self._phone = phone
        self._password = password
        self._ws_url = ws_url
        self.bot: SelfBot | None = None

    async def activate(self) -> SelfBot:
        """فعال‌سازی و اتصال. بدون ack_risk استثنا می‌دهد."""
        if not self.enabled:
            raise HybridDisabledError(
                "Self-bot فعال نیست. برای فعال‌سازی آگاهانه: "
                "HybridPlugin(enabled=True, ack_risk=True)"
            )
        kwargs: dict[str, object] = {}
        if self._ws_url:
            kwargs["ws_url"] = self._ws_url
        self.bot = SelfBot(
            session=self._session_arg,
            phone=self._phone,
            password=self._password,
            **kwargs,
        )
        await self.bot.connect()
        return self.bot

    async def close(self) -> None:
        if self.bot is not None:
            await self.bot.close()
            self.bot = None

    @property
    def lane(self) -> str:
        return self._lane_name

    def register_rpc(self, name: str, spec: RpcSpec) -> None:
        """ثبت یک RPC جدید در رجیستری (فقط وقتی لایه فعال است)."""
        if not self.enabled:
            raise HybridDisabledError("Self-bot فعال نیست")
        registry.register(spec)

    async def iter_messages(self, chat_id: object, limit: int = 50):
        """خواندن تاریخچه پیام‌ها — پیاده‌سازی واقعی."""
        if not self.enabled:
            raise HybridDisabledError("Self-bot فعال نیست")
        if self.bot is None:
            raise HybridDisabledError("اول activate() صدا بزن")
        async for msg in self.bot.iter_messages(chat_id, limit=limit):
            yield msg


__all__ = [
    "AuthError",
    "AuthFlow",
    "CodeRequest",
    "Dialog",
    "HYBRID_WARNING",
    "HybridDisabledError",
    "HybridPlugin",
    "MESSAGE_BODY_SCHEMA",
    "Message",
    "NotConnected",
    "PEER_SCHEMA",
    "PEER_TYPE",
    "Peer",
    "ProtoError",
    "RpcFailed",
    "RpcRegistry",
    "RpcSpec",
    "RpcTimeout",
    "SelfBot",
    "SelfBotError",
    "Session",
    "SessionError",
    "SessionStore",
    "SessionManager",
    "SessionManagerError",
    "AccountInfo",
    "CheckReport",
    "CreateResult",
    "SignInResult",
    "Transport",
    "TransportError",
    "build",
    "decode",
    "decode_response",
    "device_fingerprint",
    "encode_named",
    "encode_request",
    "frame_length_prefixed",
    "hybrid_warning",
    "interactive_login",
    "make_chat",
    "make_document_content",
    "make_inline_keyboard",
    "make_peer",
    "make_text_content",
    "normalize_phone",
    "registry",
    "unframe_length_prefixed",
]
