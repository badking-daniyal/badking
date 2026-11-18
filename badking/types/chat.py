"""Chat و ChatFullInfo — منبع: docs.bale.ai/#chat , #chatfullinfo"""

from __future__ import annotations

from typing import Literal

from .common import BaleModel
from .user import User

ChatType = Literal["private", "group", "supergroup", "channel"]


class Chat(BaleModel):
    id: int
    type: ChatType
    title: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_forum: bool | None = None

    @property
    def is_private(self) -> bool:
        return self.type == "private"


class ChatFullInfo(Chat):
    photo: object | None = None
    name: str | None = None
    description: str | None = None
    invite_link: str | None = None
    pinned_message: object | None = None
    permissions: object | None = None
    slow_mode_delay: int | None = None
    sticker_set_name: str | None = None
    can_set_sticker_set: bool | None = None
    linked_chat_id: int | None = None
    location: object | None = None
    members: list[object] | None = None
    member_count: int | None = None
    administrators: list[object] | None = None
