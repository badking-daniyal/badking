"""ContextVar نگهدارنده Bot جاری برای متدهای راحت مثل Message.answer()."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..core.bot import Bot

current_bot: ContextVar[Optional["Bot"]] = ContextVar("badking_current_bot", default=None)
current_update: ContextVar[Optional[object]] = ContextVar("badking_current_update", default=None)
