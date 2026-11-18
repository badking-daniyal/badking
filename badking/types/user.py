"""User — کاربر بله یا بازو. منبع: docs.bale.ai/#user"""

from __future__ import annotations

from .common import BaleModel


class User(BaleModel):
    id: int
    is_bot: bool = False
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    can_join_groups: bool | None = None
    can_read_all_group_messages: bool | None = None
    supports_inline_queries: bool | None = None

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p)

    @property
    def mention(self) -> str:
        if self.username:
            return f"@{self.username}"
        return f"[{self.full_name}](uid:{self.id})"
