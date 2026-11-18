"""کیبوردها و دکمهها — منبع: docs.bale.ai (#replykeyboardmarkup, #inlinekeyboardbutton, ...)"""

from __future__ import annotations

from typing import Any

from .common import BaleModel


class WebAppInfo(BaleModel):
    url: str


class CopyTextButton(BaleModel):
    text: str


class KeyboardButton(BaleModel):
    text: str
    request_contact: bool | None = None
    request_location: bool | None = None
    web_app: WebAppInfo | dict[str, Any] | None = None
    style: str | None = None


class InlineKeyboardButton(BaleModel):
    text: str
    url: str | None = None
    callback_data: str | None = None
    web_app: WebAppInfo | dict[str, Any] | None = None
    copy_text: CopyTextButton | dict[str, Any] | None = None
    style: str | None = None


class ReplyKeyboardMarkup(BaleModel):
    keyboard: list[list[KeyboardButton | str]]
    resize_keyboard: bool | None = None
    one_time_keyboard: bool | None = None
    selective: bool | None = None
    input_field_placeholder: str | None = None


class InlineKeyboardMarkup(BaleModel):
    inline_keyboard: list[list[InlineKeyboardButton]]


class ReplyKeyboardRemove(BaleModel):
    remove_keyboard: bool = True
    selective: bool | None = None
