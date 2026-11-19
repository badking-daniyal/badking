"""
BADKING — فریمورک همه‌کاره و AI-Native برای بازوهای بله.

سه لایه دسترسی:
  • لایه صفر (بدون کد): Flow Builder، CLI، پنل ادمین
  • لایه بالا (پایتون): Dispatcher، FSM، filters، middleware
  • لایه خام: دسترسی مستقیم به تمام متدهای Bot API و JSON خام

مستندات رسمی بله: https://docs.bale.ai/
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    "__version__",
    "Bot",
    "Dispatcher",
    "F",
    "Router",
    "Message",
    "CallbackQuery",
    "Update",
    "User",
    "Chat",
]

from .core.bot import Bot
from .core.dispatcher import Dispatcher
from .core.router import Router
from .filters.magic import F
from .types.update import Update
from .types.user import User
from .types.chat import Chat
from .types.message import Message
from .types.callback import CallbackQuery

# هسته و خطاها
from .core.constants import API_BASE, Limits
from .core.errors import BaleError, NetworkError, RateLimitError, StopPropagation, UnauthorizedError

# FSM و ذخیرهسازی
from .fsm import FSMContext, State, StatesGroup
from .storage import MemoryStorage, SQLiteStorage

# قابلیتهای بله
from .miniapp import validate_init_data
from .safir import SafirClient
from .payments import PaymentToolkit
from .business import BusinessBot
from .ratelimit import RateLimiter
from .recovery import OffsetStore

# هوش مصنوعی
from .ai import AIAssistant, EchoLLM, IntentRouter, Memory, OpenAICompatibleLLM, SimpleRAG

# بدونکد و Adapter
from .flows import Flow
from .adapters import AdapterRegistry, BaleAdapter

# مکالمه و صفحهبندی
from .conversation import Conversation, ConversationManager, ConversationTimeout
from .keyboards import (
    InlineKeyboardBuilder,
    KeyboardPaginator,
    ReplyKeyboardBuilder,
)

# enum های پروتکل
from .enums import (
    AuthErrors,
    ChatType,
    GiftOpenning,
    GivingType,
    GroupType,
    ListLoadMode,
    PeerSource,
    PeerType,
    PrivacyMode,
    ReportKind,
    Restriction,
    SendCodeType,
    SendType,
    TypingMode,
)

# ابزارها
from .utils import (
    Throttle,
    create_progress_bar,
    decode_int64_list,
    encode_int64_list,
    extract_join_token,
    extract_username,
    format_bytes,
    generate_id,
    normalize_phone,
    random_id,
    smart_split_text,
    split_by_length,
    to_english_digits,
    to_persian_digits,
)
from .utils.callback_data import CallbackData, CallbackFilter

# موتور تاب‌آوری
from .resilience import (
    Backoff,
    CircuitBreaker,
    CircuitState,
    RequestQueue,
    ResilientCaller,
    RetryPolicy,
)

# خطاها
from .core.errors import (
    BADKINGError,
    AuthenticationError,
    ChatNotFoundError,
    ChatWriteForbiddenError,
    CircuitOpenError,
    CodeInvalidError,
    ConfigError,
    ConnectionLostError,
    DecodeError,
    DnsError,
    DownloadFailedError,
    EncodeError,
    FileTooLargeError,
    FloodWaitError,
    InvalidPeerError,
    MediaError,
    MessageError,
    MessageNotFoundError,
    MessageTooLongError,
    MissingParameterError,
    MissingTokenError,
    NotAdminError,
    PasswordNeededError,
    PermissionError_,
    ProtocolError,
    ReplyNotFoundError,
    RpcFailedError,
    SessionError,
    SessionExpiredError,
    StorageError,
    StorageLockedError,
    TimeoutError_,
    TlsError,
    UnknownMethodError,
    UnsupportedMediaError,
    UploadFailedError,
    UserNotFoundError,
    ValidationError,
    format_exception,
)

# زیرساخت
from .connectors import Auth, Connector
from .jobs import JobQueue, Scheduler
from .events import EventBus
from .orm import Store
from .media import OCR, Voice

# کیفیت و امنیت
from .observability import Metrics, metrics
from .security import AntiSpam, AuditLog, Captcha, RBAC, Secrets
from .testing import DryBot, Health
from .middleware import antispam_mw, logging_mw, metrics_mw
from .methods import KNOWN_METHODS

__all__ += [
    "API_BASE", "Limits", "BaleError", "NetworkError", "RateLimitError", "UnauthorizedError", "StopPropagation",
    "FSMContext", "State", "StatesGroup", "MemoryStorage", "SQLiteStorage",
    "validate_init_data", "SafirClient", "PaymentToolkit", "BusinessBot",
    "RateLimiter", "OffsetStore",
    "AIAssistant", "EchoLLM", "IntentRouter", "Memory", "OpenAICompatibleLLM", "SimpleRAG",
    "Flow", "AdapterRegistry", "BaleAdapter",
    "Conversation", "ConversationManager", "ConversationTimeout", "KeyboardPaginator",
    "InlineKeyboardBuilder", "ReplyKeyboardBuilder", "CallbackData", "CallbackFilter",
    "PeerType", "ChatType", "GroupType", "ListLoadMode", "TypingMode", "SendType",
    "PrivacyMode", "Restriction", "ReportKind", "GivingType", "GiftOpenning",
    "PeerSource", "SendCodeType", "AuthErrors",
    "Throttle", "smart_split_text", "split_by_length", "generate_id", "random_id",
    "extract_join_token", "extract_username", "decode_int64_list", "encode_int64_list",
    "format_bytes", "create_progress_bar", "to_persian_digits", "to_english_digits",
    "normalize_phone",
    "RetryPolicy", "Backoff", "CircuitBreaker", "CircuitState",
    "RequestQueue", "ResilientCaller",
    "BADKINGError", "AuthenticationError", "ChatNotFoundError", "ChatWriteForbiddenError",
    "CircuitOpenError", "CodeInvalidError", "ConfigError", "ConnectionLostError",
    "DecodeError", "DnsError", "DownloadFailedError", "EncodeError", "FileTooLargeError",
    "FloodWaitError", "InvalidPeerError", "MediaError", "MessageError", "MessageNotFoundError",
    "MessageTooLongError", "MissingParameterError", "MissingTokenError", "NotAdminError",
    "PasswordNeededError", "PermissionError_", "ProtocolError", "ReplyNotFoundError",
    "RpcFailedError", "SessionError", "SessionExpiredError", "StorageError", "StorageLockedError",
    "TimeoutError_", "TlsError", "UnknownMethodError", "UnsupportedMediaError",
    "UploadFailedError", "UserNotFoundError", "ValidationError", "format_exception",
    "Auth", "Connector", "JobQueue", "Scheduler", "EventBus", "Store", "OCR", "Voice",
    "Metrics", "metrics", "AntiSpam", "AuditLog", "Captcha", "RBAC", "Secrets",
    "DryBot", "Health", "logging_mw", "metrics_mw", "antispam_mw", "KNOWN_METHODS",
    "SelfBot", "HybridPlugin", "SessionStore", "hybrid_warning",
]


_LAZY_HYBRID = {
    "SelfBot": "client",
    "HybridPlugin": "plugin",
    "HybridDisabledError": "plugin",
    "SessionStore": "session",
    "Session": "session",
    "hybrid_warning": "plugin",
    "registry": "rpc",
    "RpcSpec": "rpc",
    "RpcRegistry": "rpc",
}


def __getattr__(name: str):
    """بارگذاری تنبل لایه hybrid.

    این کار باعث می‌شود `from badking import SelfBot` کار کند، بدون اینکه
    نصب بودن websockets برای کسی که فقط ربات رسمی می‌خواهد اجباری شود.
    """
    module_name = _LAZY_HYBRID.get(name)
    if module_name is None:
        raise AttributeError(f"module 'badking' has no attribute {name!r}")
    import importlib

    module = importlib.import_module(f".hybrid.{module_name}", __name__)
    return getattr(module, name)
