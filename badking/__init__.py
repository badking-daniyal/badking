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
    "Auth", "Connector", "JobQueue", "Scheduler", "EventBus", "Store", "OCR", "Voice",
    "Metrics", "metrics", "AntiSpam", "AuditLog", "Captcha", "RBAC", "Secrets",
    "DryBot", "Health", "logging_mw", "metrics_mw", "antispam_mw", "KNOWN_METHODS",
]
