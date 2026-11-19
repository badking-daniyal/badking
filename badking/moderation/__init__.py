"""Moderation Engine — اخطار، سکوت، اخراج، فیلتر، لاگ.

    from badking.moderation import Moderator, Rule

    mod = Moderator(bot, storage=SQLiteStorage("mod.db"))

    mod.add_rule(Rule(name="links", pattern=r"https?://", action="warn"))
    mod.add_rule(Rule(name="spam", words=["کسب درآمد", "کلیک کنید"], action="mute"))

    @bot.on_message(F.text)
    async def check(message):
        await mod.inspect(message)

قاعده مهم: هر اقدام ثبت می‌شود. اگر از کاربر بپرسند «چرا اخراج شدم؟»،
جواب داری.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("badking.moderation")

from .monitor import ChannelMonitor, ChannelStats, MemberEvent


class Action(str, Enum):
    """اقدام ممکن."""

    WARN = "warn"
    MUTE = "mute"
    BAN = "ban"
    KICK = "kick"
    DELETE = "delete"
    NOTHING = "nothing"


class ModerationError(Exception):
    """خطای مدیریت، با راهنمای رفع."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message}\n  → {self.hint}" if self.hint else self.message


@dataclass
class Rule:
    """یک قاعده.

    دقیقاً یکی از این‌ها را بده:

    - ``pattern``: الگوی regex
    - ``words``: فهرست کلمات ممنوع
    - ``max_length``: حداکثر طول متن
    - ``max_links``: حداکثر تعداد لینک
    - ``max_files``: حداکثر تعداد فایل در پیام
    - ``max_mentions``: حداکثر منشن

    Args:
        action: چه کاری بکن.
        severity: ۱ تا ۳. برای escalation.
        exempt_admins: ادمین‌ها معاف باشند.
        message: پیامی که به کاربر گفته شود.
    """

    name: str
    action: Action = Action.WARN
    severity: int = 1
    pattern: str = ""
    words: list[str] = field(default_factory=list)
    max_length: int = -1
    max_links: int = -1
    max_files: int = -1
    max_mentions: int = -1
    exempt_admins: bool = True
    message: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.action, str):
            self.action = Action(self.action)

        # -1 یعنی «این شرط را نگذار». صفر یک مقدار معتبر است: «هیچ فایلی
        # مجاز نیست». اگر پیش‌فرض صفر بود، نمی‌شد این دو را از هم تفکیک کرد.
        # توجه: صفر در پایتون falsy است، پس نمی‌شود از `if value` استفاده کرد.
        limits = (self.max_length, self.max_links, self.max_files, self.max_mentions)
        checks = sum(1 for value in limits if value != -1)
        if self.pattern:
            checks += 1
        if self.words:
            checks += 1

        if checks == 0:
            raise ModerationError(
                f"قاعده {self.name!r} هیچ شرطی ندارد",
                hint="یکی از pattern / words / max_length / max_links / ... را بده.",
            )

        if self.pattern:
            try:
                self._compiled = re.compile(self.pattern, re.IGNORECASE)
            except re.error as exc:
                raise ModerationError(
                    f"الگوی قاعده {self.name!r} خراب است: {exc}",
                    hint="regex را چک کن.",
                ) from exc
        else:
            self._compiled = None

    def matches(self, text: str, *, links: int = 0, files: int = 0, mentions: int = 0) -> bool:
        """آیا این پیام قاعده را نقض می‌کند؟"""
        if self._compiled and text and self._compiled.search(text):
            return True

        if self.words:
            lowered = text.lower()
            if any(word.lower() in lowered for word in self.words):
                return True

        if self.max_length >= 0 and len(text) > self.max_length:
            return True

        if self.max_links >= 0 and links > self.max_links:
            return True

        if self.max_files >= 0 and files > self.max_files:
            return True

        if self.max_mentions >= 0 and mentions > self.max_mentions:
            return True

        return False


@dataclass
class Violation:
    """یک تخلف ثبت‌شده."""

    user_id: int
    chat_id: int
    rule: str
    action: Action
    at: float = field(default_factory=time.time)
    text: str = ""
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "rule": self.rule,
            "action": self.action.value,
            "at": self.at,
            "text": self.text[:200],
            "resolved": self.resolved,
        }


class Moderator:
    """موتور مدیریت.

    Args:
        bot: کلاینت.
        storage: جایی برای ذخیره تخلف‌ها. اگر ``None`` باشد، در حافظه.
        warn_limit: چند اخطار تا اخراج خودکار. صفر یعنی بی‌نهایت.
        mute_seconds: مدت سکوت پیش‌فرض.
    """

    def __init__(
        self,
        bot: Any = None,
        *,
        storage: Any = None,
        warn_limit: int = 3,
        mute_seconds: int = 3600,
    ) -> None:
        self.bot = bot
        self.storage = storage
        self.warn_limit = warn_limit
        self.mute_seconds = mute_seconds
        self.rules: dict[str, Rule] = {}
        self._violations: list[Violation] = []
        self._warns: dict[tuple[int, int], int] = {}
        self._whitelist: set[int] = set()
        self._blacklist: set[int] = set()

    # ---------- قواعد ----------

    def add_rule(self, rule: Rule) -> None:
        """قاعده اضافه می‌کند. نام تکراری جایگزین می‌شود."""
        self.rules[rule.name] = rule

    def remove_rule(self, name: str) -> bool:
        """قاعده را حذف می‌کند."""
        return self.rules.pop(name, None) is not None

    def rule_names(self) -> list[str]:
        return list(self.rules)

    # ---------- لیست‌ها ----------

    def whitelist(self, user_id: int) -> None:
        """این کاربر هرگز بررسی نمی‌شود."""
        self._whitelist.add(user_id)
        self._blacklist.discard(user_id)

    def blacklist(self, user_id: int) -> None:
        """این کاربر مستقیم اخراج می‌شود."""
        self._blacklist.add(user_id)
        self._whitelist.discard(user_id)

    def unlist(self, user_id: int) -> None:
        """از هر دو لیست خارج می‌کند."""
        self._whitelist.discard(user_id)
        self._blacklist.discard(user_id)

    def is_whitelisted(self, user_id: int) -> bool:
        return user_id in self._whitelist

    def is_blacklisted(self, user_id: int) -> bool:
        return user_id in self._blacklist

    # ---------- بررسی ----------

    async def inspect(self, message: Any) -> list[Violation]:
        """پیام را بررسی می‌کند و اقدام لازم را انجام می‌دهد.

        فهرست تخلف‌های پیداشده را برمی‌گرداند. خالی یعنی پاک بود.
        """
        user = getattr(message, "from_user", None)
        chat = getattr(message, "chat", None)
        if not user or not chat:
            return []

        user_id = user.id
        chat_id = chat.id

        if self.is_whitelisted(user_id):
            return []

        # ادمین‌ها معاف
        if await self._is_admin(chat_id, user_id):
            return []

        text = getattr(message, "text", "") or getattr(message, "caption", "") or ""
        links = len(re.findall(r"https?://|t\.me/|@\w+", text))
        files = 1 if getattr(message, "document", None) or getattr(message, "photo", None) else 0
        mentions = text.count("@")

        found: list[Violation] = []

        # لیست سیاه
        if self.is_blacklisted(user_id):
            violation = Violation(
                user_id=user_id,
                chat_id=chat_id,
                rule="blacklist",
                action=Action.BAN,
                text=text,
            )
            found.append(violation)
            await self._apply(violation, message)
            return found

        for rule in self.rules.values():
            if not rule.matches(text, links=links, files=files, mentions=mentions):
                continue

            violation = Violation(
                user_id=user_id,
                chat_id=chat_id,
                rule=rule.name,
                action=rule.action,
                text=text,
            )
            found.append(violation)
            await self._apply(violation, message, rule=rule)

        return found

    async def _apply(
        self,
        violation: Violation,
        message: Any,
        *,
        rule: Rule | None = None,
    ) -> None:
        """اقدام را انجام می‌دهد و ثبت می‌کند."""
        action = violation.action
        user_id = violation.user_id
        chat_id = violation.chat_id

        try:
            if action == Action.DELETE:
                await self._call("delete_message", chat_id, getattr(message, "message_id", 0))

            elif action == Action.WARN:
                count = self._warns.get((chat_id, user_id), 0) + 1
                self._warns[(chat_id, user_id)] = count

                text = (rule.message if rule and rule.message else "") or (
                    f"اخطار {count}"
                    + (f" از {self.warn_limit}" if self.warn_limit else "")
                )
                await self._call("send_message", chat_id, text)

                if self.warn_limit and count >= self.warn_limit:
                    log.info("کاربر %d به حد اخطار رسید — اخراج", user_id)
                    await self._call("ban_chat_member", chat_id, user_id)
                    violation.action = Action.BAN
                    self._warns.pop((chat_id, user_id), None)

            elif action == Action.MUTE:
                await self._call(
                    "restrict_chat_member",
                    chat_id,
                    user_id,
                    until_date=int(time.time()) + self.mute_seconds,
                )

            elif action == Action.BAN:
                await self._call("ban_chat_member", chat_id, user_id)

            elif action == Action.KICK:
                await self._call("ban_chat_member", chat_id, user_id)
                await self._call("unban_chat_member", chat_id, user_id)

        except Exception as exc:  # noqa: BLE001
            log.error("اقدام %s روی %d شکست خورد: %s", action.value, user_id, exc)

        self._violations.append(violation)
        await self._persist(violation)

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """متد کلاینت را صدا می‌زند، اگر بود."""
        if not self.bot:
            return None
        func = getattr(self.bot, method, None)
        if func is None:
            log.debug("کلاینت متد %s ندارد — رد شد", method)
            return None
        return await func(*args, **kwargs)

    async def _is_admin(self, chat_id: int, user_id: int) -> bool:
        """آیا این کاربر ادمین است؟ اگر ندانیم، خیر."""
        if not self.bot:
            return False

        func = getattr(self.bot, "get_chat_member", None)
        if func is None:
            return False

        try:
            member = await func(chat_id, user_id)
            status = getattr(member, "status", "")
            return status in {"creator", "administrator", "admin"}
        except Exception:  # noqa: BLE001
            return False

    # ---------- تاریخچه ----------

    async def _persist(self, violation: Violation) -> None:
        if not self.storage:
            return
        try:
            key = f"mod:{violation.chat_id}:{violation.user_id}"
            existing = await self.storage.get(key) or {"history": []}
            history = existing.get("history", [])
            history.append(violation.to_dict())
            # فقط ۱۰۰ مورد آخر
            await self.storage.set(key, {"history": history[-100:]})
        except Exception as exc:  # noqa: BLE001
            log.warning("ثبت تخلف نشد: %s", exc)

    def violations(self, *, user_id: int | None = None, chat_id: int | None = None) -> list[Violation]:
        """تخلف‌ها، با فیلتر اختیاری."""
        out = self._violations
        if user_id is not None:
            out = [v for v in out if v.user_id == user_id]
        if chat_id is not None:
            out = [v for v in out if v.chat_id == chat_id]
        return list(out)

    def warn_count(self, chat_id: int, user_id: int) -> int:
        """چند اخطار دارد؟"""
        return self._warns.get((chat_id, user_id), 0)

    def reset_warns(self, chat_id: int, user_id: int) -> None:
        """اخطارها را صفر می‌کند (بخشش)."""
        self._warns.pop((chat_id, user_id), None)

    def stats(self) -> dict[str, Any]:
        """خلاصه وضعیت."""
        by_action: dict[str, int] = {}
        for violation in self._violations:
            by_action[violation.action.value] = by_action.get(violation.action.value, 0) + 1

        return {
            "rules": len(self.rules),
            "violations": len(self._violations),
            "by_action": by_action,
            "whitelisted": len(self._whitelist),
            "blacklisted": len(self._blacklist),
            "warned_users": len(self._warns),
        }


# ---------- قواعد آماده ----------

def link_rule(action: Action = Action.WARN) -> Rule:
    """هر لینکی را می‌گیرد."""
    return Rule(name="links", pattern=r"https?://|www\.", action=action)


def flood_rule(max_length: int = 4000, action: Action = Action.WARN) -> Rule:
    """متن خیلی بلند."""
    return Rule(name="flood", max_length=max_length, action=action)


def mention_spam_rule(max_mentions: int = 5, action: Action = Action.MUTE) -> Rule:
    """منشن انبوه."""
    return Rule(name="mention_spam", max_mentions=max_mentions, action=action)


def word_rule(words: list[str], action: Action = Action.WARN) -> Rule:
    """کلمات ممنوع."""
    return Rule(name="banned_words", words=words, action=action)


__all__ = [
    "Action",
    "ChannelMonitor",
    "ChannelStats",
    "MemberEvent",
    "ModerationError",
    "Moderator",
    "Rule",
    "Violation",
    "flood_rule",
    "link_rule",
    "mention_spam_rule",
    "word_rule",
]
