"""Channel Monitor — ورود، خروج، آمار، گزارش دوره‌ای.

    from badking.moderation import ChannelMonitor

    monitor = ChannelMonitor(storage=SQLiteStorage("monitor.db"))
    monitor.watch(-1001234567890, admin_id=111)

    @bot.on_message(F.new_chat_members)
    async def joined(message):
        await monitor.record_join(message.chat.id, message.new_chat_members[0])

    report = await monitor.report(-1001234567890, days=7)

محدودیت شفاف: بله رویداد «عضو جدید» را می‌دهد ولی برای هر عضو خروجی،
فقط وقتی که خودش پیام خروج بفرستد یا ربات ببیند. اگر API چیزی نداد،
اینجا چیزی ساخته نمی‌شود. آمار بر اساس چیزی است که واقعاً دیدیم، نه
حدس.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("badking.moderation.monitor")


@dataclass
class MemberEvent:
    """یک رویداد عضویت."""

    chat_id: int
    user_id: int
    kind: str  # "join" یا "leave"
    at: float = field(default_factory=time.time)
    name: str = ""
    username: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "kind": self.kind,
            "at": self.at,
            "name": self.name,
            "username": self.username,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemberEvent":
        return cls(
            chat_id=data["chat_id"],
            user_id=data["user_id"],
            kind=data["kind"],
            at=data.get("at", 0.0),
            name=data.get("name", ""),
            username=data.get("username", ""),
        )


@dataclass
class ChannelStats:
    """آمار یک بازه."""

    chat_id: int
    days: int
    joins: int
    leaves: int
    unique_joiners: int
    unique_leavers: int

    @property
    def net(self) -> int:
        """رشد خالص."""
        return self.joins - self.leaves

    @property
    def churn(self) -> float:
        """نسبت خروج به ورود. بالای ۱ یعنی کانال آب می‌رود."""
        if self.joins == 0:
            return float(self.leaves)
        return round(self.leaves / self.joins, 2)

    def summary(self) -> str:
        """خلاصه خوانا."""
        arrow = "↑" if self.net >= 0 else "↓"
        return (
            f"{self.days} روز اخیر:\n"
            f"  ورود: {self.joins} ({self.unique_joiners} نفر یکتا)\n"
            f"  خروج: {self.leaves} ({self.unique_leavers} نفر یکتا)\n"
            f"  خالص: {arrow} {abs(self.net)}"
        )


class ChannelMonitor:
    """نظارت بر یک یا چند کانال.

    Args:
        storage: جایی برای نگه‌داشتن رویدادها. ``None`` یعنی در حافظه.
        max_events: حداکثر رویداد نگه‌داشته‌شده در حافظه برای هر کانال.
    """

    def __init__(self, *, storage: Any = None, max_events: int = 5000) -> None:
        self.storage = storage
        self.max_events = max_events
        self._events: dict[int, list[MemberEvent]] = {}
        self._admins: dict[int, set[int]] = {}
        self._names: dict[int, str] = {}

    # ---------- ثبت کانال ----------

    def watch(self, chat_id: int, *, admin_id: int | None = None, name: str = "") -> None:
        """کانال را زیر نظر می‌گیرد.

        Args:
            chat_id: شناسه عددی کانال.
            admin_id: کسی که گزارش‌ها برایش برود.
            name: نام نمایشی.
        """
        self._events.setdefault(chat_id, [])
        if admin_id is not None:
            self._admins.setdefault(chat_id, set()).add(admin_id)
        if name:
            self._names[chat_id] = name

    def unwatch(self, chat_id: int) -> bool:
        """از نظارت خارج می‌کند."""
        self._admins.pop(chat_id, None)
        self._names.pop(chat_id, None)
        return self._events.pop(chat_id, None) is not None

    def watched(self) -> list[int]:
        """کانال‌های زیر نظر."""
        return list(self._events)

    def admins_of(self, chat_id: int) -> set[int]:
        """ادمین‌های این کانال."""
        return set(self._admins.get(chat_id, set()))

    def name_of(self, chat_id: int) -> str:
        """نام نمایشی."""
        return self._names.get(chat_id, str(chat_id))

    # ---------- ثبت رویداد ----------

    async def record_join(self, chat_id: int, user: Any) -> MemberEvent:
        """ثبت ورود عضو."""
        return await self._record(chat_id, user, "join")

    async def record_leave(self, chat_id: int, user: Any) -> MemberEvent:
        """ثبت خروج عضو."""
        return await self._record(chat_id, user, "leave")

    async def _record(self, chat_id: int, user: Any, kind: str) -> MemberEvent:
        event = MemberEvent(
            chat_id=chat_id,
            user_id=getattr(user, "id", 0),
            kind=kind,
            name=getattr(user, "first_name", "") or "",
            username=getattr(user, "username", "") or "",
        )

        bucket = self._events.setdefault(chat_id, [])
        bucket.append(event)

        # سقف حافظه
        if len(bucket) > self.max_events:
            del bucket[: len(bucket) - self.max_events]

        await self._persist(event)
        return event

    async def _persist(self, event: MemberEvent) -> None:
        if not self.storage:
            return
        try:
            key = f"monitor:{event.chat_id}"
            data = await self.storage.get(key) or {"events": []}
            events = data.get("events", [])
            events.append(event.to_dict())
            await self.storage.set(key, {"events": events[-self.max_events:]})
        except Exception as exc:  # noqa: BLE001
            log.warning("ثبت رویداد نشد: %s", exc)

    async def load(self, chat_id: int) -> int:
        """رویدادها را از storage بار می‌کند. تعداد را برمی‌گرداند."""
        if not self.storage:
            return 0

        try:
            data = await self.storage.get(f"monitor:{chat_id}")
        except Exception as exc:  # noqa: BLE001
            log.warning("بارگذاری رویدادها نشد: %s", exc)
            return 0

        if not data:
            return 0

        events = [MemberEvent.from_dict(e) for e in data.get("events", [])]
        self._events[chat_id] = events
        return len(events)

    # ---------- گزارش ----------

    def events(
        self,
        chat_id: int,
        *,
        days: float | None = None,
        kind: str | None = None,
    ) -> list[MemberEvent]:
        """رویدادها با فیلتر."""
        out = self._events.get(chat_id, [])

        if days is not None:
            cutoff = time.time() - days * 86400
            out = [e for e in out if e.at >= cutoff]

        if kind:
            out = [e for e in out if e.kind == kind]

        return list(out)

    def stats(self, chat_id: int, *, days: int = 7) -> ChannelStats:
        """آمار بازه."""
        events = self.events(chat_id, days=days)

        joins = [e for e in events if e.kind == "join"]
        leaves = [e for e in events if e.kind == "leave"]

        return ChannelStats(
            chat_id=chat_id,
            days=days,
            joins=len(joins),
            leaves=len(leaves),
            unique_joiners=len({e.user_id for e in joins}),
            unique_leavers=len({e.user_id for e in leaves}),
        )

    async def report(self, chat_id: int, *, days: int = 7) -> str:
        """گزارش خوانا برای فرستادن به ادمین."""
        stats = self.stats(chat_id, days=days)
        header = f"گزارش {self.name_of(chat_id)}\n"
        return header + stats.summary()

    def daily_breakdown(self, chat_id: int, *, days: int = 7) -> list[dict[str, Any]]:
        """آمار روز به روز.

        روز ۰ امروز است (۲۴ ساعت گذشته)، روز ۱ دیروز، و به همین ترتیب.
        """
        now = time.time()
        out = []

        for offset in range(days):
            end = now - offset * 86400
            start = end - 86400
            bucket = [e for e in self._events.get(chat_id, []) if start <= e.at <= end]
            out.append(
                {
                    "day": offset,
                    "joins": sum(1 for e in bucket if e.kind == "join"),
                    "leaves": sum(1 for e in bucket if e.kind == "leave"),
                }
            )

        return out

    def top_growth(self, *, days: int = 7) -> list[tuple[int, int]]:
        """کانال‌ها به ترتیب رشد خالص."""
        scored = [(chat_id, self.stats(chat_id, days=days).net) for chat_id in self._events]
        return sorted(scored, key=lambda pair: pair[1], reverse=True)

    def dashboard(self) -> dict[str, Any]:
        """خلاصه همه کانال‌ها."""
        return {
            "channels": len(self._events),
            "total_events": sum(len(v) for v in self._events.values()),
            "per_channel": {
                self.name_of(chat_id): {
                    "events": len(events),
                    "joins": sum(1 for e in events if e.kind == "join"),
                    "leaves": sum(1 for e in events if e.kind == "leave"),
                }
                for chat_id, events in self._events.items()
            },
        }


__all__ = ["ChannelMonitor", "ChannelStats", "MemberEvent"]
