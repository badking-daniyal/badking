"""تست سطح عمومی: هر چیزی که در README و سایت وعده داده شده باید import شود.

این تست همان کاری را می‌کند که کاربر تازه انجام می‌دهد: `from badking import X`.
اگر روزی کسی export را بشکند، اینجا قرمز می‌شود، نه در Issue کاربر.
"""

from __future__ import annotations

import importlib

import pytest


# ---------- سطح بسته ----------

PUBLIC_API = [
    # هسته
    "Bot", "Dispatcher", "Router", "F",
    # FSM
    "State", "StatesGroup", "FSMContext", "MemoryStorage", "SQLiteStorage",
    # کیبورد
    "KeyboardPaginator", "InlineKeyboardBuilder", "ReplyKeyboardBuilder",
    "CallbackData", "CallbackFilter",
    # enum
    "PeerType", "ChatType", "GroupType", "ListLoadMode", "TypingMode",
    "SendType", "PrivacyMode", "Restriction", "ReportKind", "GivingType",
    "GiftOpenning", "PeerSource", "SendCodeType", "AuthErrors",
    # ابزار
    "Throttle", "smart_split_text", "split_by_length", "generate_id",
    "random_id", "extract_join_token", "extract_username",
    "decode_int64_list", "encode_int64_list", "format_bytes",
    "create_progress_bar", "to_persian_digits", "to_english_digits",
    "normalize_phone",
    # تاب‌آوری
    "RetryPolicy", "Backoff", "CircuitBreaker", "CircuitState",
    "RequestQueue", "ResilientCaller",
    # خطا
    "BADKINGError", "AuthenticationError", "ChatNotFoundError",
    "ChatWriteForbiddenError", "CircuitOpenError", "CodeInvalidError",
    "ConfigError", "ConnectionLostError", "DecodeError", "DnsError",
    "DownloadFailedError", "EncodeError", "FileTooLargeError",
    "FloodWaitError", "InvalidPeerError", "MediaError", "MessageError",
    "MessageNotFoundError", "MessageTooLongError", "MissingParameterError",
    "MissingTokenError", "NotAdminError", "PasswordNeededError",
    "PermissionError_", "ProtocolError", "ReplyNotFoundError",
    "RpcFailedError", "SessionError", "SessionExpiredError", "StorageError",
    "StorageLockedError", "TimeoutError_", "TlsError", "UnknownMethodError",
    "UnsupportedMediaError", "UploadFailedError", "UserNotFoundError",
    "ValidationError", "format_exception",
    # زیرساخت
    "Auth", "Connector", "JobQueue", "Scheduler", "EventBus", "Store",
    "OCR", "Voice", "Metrics", "metrics",
    "AntiSpam", "AuditLog", "Captcha", "RBAC", "Secrets",
    "DryBot", "Health", "logging_mw", "metrics_mw", "antispam_mw",
    # هوش مصنوعی
    "AIAssistant", "EchoLLM", "IntentRouter", "Memory",
    "OpenAICompatibleLLM", "SimpleRAG",
    # پرداخت و جریان
    "PaymentToolkit", "SafirClient", "BusinessBot", "Flow",
    "AdapterRegistry", "BaleAdapter",
    "Conversation", "ConversationManager", "ConversationTimeout",
    "RateLimiter", "OffsetStore", "validate_init_data", "KNOWN_METHODS",
]


class TestPublicAPI:
    @pytest.mark.parametrize("name", PUBLIC_API)
    def test_importable_from_package(self, name):
        import badking

        assert hasattr(badking, name), f"badking.{name} وجود ندارد"

    def test_all_matches_reality(self):
        import badking

        missing = [n for n in badking.__all__ if not hasattr(badking, n)]
        assert missing == [], f"در __all__ هست ولی وجود ندارد: {missing}"

    def test_no_duplicate_exports(self):
        import badking

        assert len(badking.__all__) == len(set(badking.__all__))

    def test_public_api_is_exported(self):
        import badking

        not_exported = [n for n in PUBLIC_API if n not in badking.__all__]
        assert not_exported == [], f"import می‌شود ولی در __all__ نیست: {not_exported}"


# ---------- زیرماژول‌ها ----------

SUBMODULE_API = {
    "badking.fsm": ["State", "StatesGroup", "FSMContext", "MemoryStorage", "SQLiteStorage"],
    "badking.storage": ["MemoryStorage", "SQLiteStorage"],
    "badking.keyboards": [
        "KeyboardPaginator", "InlineKeyboardBuilder", "ReplyKeyboardBuilder",
    ],
    "badking.enums": ["PeerType", "ChatType", "TypingMode", "AuthErrors"],
    "badking.utils": ["smart_split_text", "normalize_phone", "Throttle"],
    "badking.core.router": ["Router"],
    "badking.filters": ["F"],
    "badking.middleware": ["logging_mw", "metrics_mw", "antispam_mw"],
    "badking.media": ["OCR", "Voice"],
    "badking.connectors": ["Auth", "Connector"],
    "badking.jobs": ["JobQueue", "Scheduler"],
    "badking.events": ["EventBus"],
    "badking.orm": ["Store"],
    "badking.security": ["AntiSpam", "AuditLog", "Captcha", "RBAC", "Secrets"],
    "badking.observability": ["Metrics", "metrics"],
    "badking.testing": ["DryBot", "Health"],
    "badking.ai": [
        "AIAssistant", "EchoLLM", "IntentRouter", "Memory",
        "OpenAICompatibleLLM", "SimpleRAG",
    ],
    "badking.payments": ["PaymentToolkit"],
    "badking.safir": ["SafirClient"],
    "badking.flows": ["Flow"],
    "badking.conversation": ["Conversation", "ConversationManager"],
    "badking.adapters": ["AdapterRegistry", "BaleAdapter"],
    "badking.cli.doctor": ["run_doctor", "run_info", "run_check", "run_test"],
    "badking.resilience": [
        "RetryPolicy", "CircuitBreaker", "RequestQueue", "ResilientCaller",
    ],
}


class TestSubmodules:
    @pytest.mark.parametrize("module_path,names", SUBMODULE_API.items())
    def test_module_exports(self, module_path, names):
        module = importlib.import_module(module_path)
        missing = [n for n in names if not hasattr(module, n)]
        assert missing == [], f"{module_path} ندارد: {missing}"

    def test_hybrid_lazy_import(self):
        # لایه self-bot باید بدون نصب websockets هم قابل import باشد
        import badking

        assert hasattr(badking, "SelfBot")
        assert hasattr(badking, "HybridPlugin")
        assert hasattr(badking, "SessionStore")
        assert hasattr(badking, "hybrid_warning")

    def test_hybrid_registry(self):
        from badking.hybrid.rpc import registry

        assert len(registry.names()) == 79


# ---------- سازگاری ----------

class TestBackwardCompat:
    def test_legacy_error_names(self):
        from badking.core.errors import BaleError, BadRequestError, StopPropagation
        from badking import BADKINGError

        assert BaleError is BADKINGError
        assert issubclass(BadRequestError, BADKINGError)
        assert issubclass(StopPropagation, Exception)

    def test_legacy_raise_for_response(self):
        from badking.core.errors import raise_for_response

        assert raise_for_response({"ok": True, "result": 5}) == 5

    def test_gift_opening_alias(self):
        from badking.enums import GiftOpenning, GiftOpening

        assert GiftOpening is GiftOpenning


# ---------- نسخه ----------

class TestVersion:
    def test_version_present(self):
        import badking

        assert hasattr(badking, "__version__")
        assert badking.__version__

    def test_version_format(self):
        import badking

        parts = badking.__version__.split(".")
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts[:2])
