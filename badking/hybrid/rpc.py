"""رجیستری RPC های self-bot.

بله صدها RPC داخلی دارد که هیچ‌کدام مستند رسمی نیستند. این ماژول یک
رجیستری قابل بازنویسی است: هر متد با نام، سرویس، و نقشه شماره فیلدهای
درخواست/پاسخ تعریف شده. اگر بله پروتکل را عوض کرد، فقط این جدول را عوض
می‌کنی — نه کل کتابخانه را.

این طراحی عمدی است: هر کتابخانه‌ای که شماره فیلدها را در کد پراکنده کند،
با اولین تغییر بله از کار می‌افتد. اینجا همه چیز در یک JSON قابل جایگزینی
است.

نحوه override:
    export BADKING_RPC_SCHEMA=/path/to/my_schema.json
یا:
    registry.load_overrides({"messaging.SendMessage": {"req": {"peer": 1}}})
"""

from __future__ import annotations

import copy
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .proto import decode, encode_named

logger = logging.getLogger("badking.hybrid.rpc")


@dataclass
class RpcSpec:
    """تعریف یک RPC."""

    name: str
    service: str
    method: str
    req: dict[str, int] = field(default_factory=dict)
    resp: dict[str, int] = field(default_factory=dict)
    doc: str = ""
    dangerous: bool = False
    needs_peer: bool = False
    nested: dict[str, Any] = field(default_factory=dict)
    resp_nested: dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return f"{self.service}.{self.method}"

    def schema(self) -> dict[str, Any]:
        """اسکیمای کامل درخواست: فیلدهای ساده + تودرتو."""
        out: dict[str, Any] = dict(self.req)
        out.update(self.nested)
        return out

    def resp_schema(self) -> dict[int, Any]:
        """اسکیمای پاسخ: {شماره فیلد: زیراسکیما}."""
        out: dict[int, Any] = {}
        for name, rule in self.resp_nested.items():
            if isinstance(rule, dict) and "field" in rule:
                out[int(rule["field"])] = _to_field_schema(rule["fields"])
        return out

    def resp_names(self) -> dict[int, str]:
        """نقشه شماره فیلد → نام، شامل فیلدهای تودرتو."""
        out: dict[int, str] = {v: k for k, v in self.resp.items()}
        for name, rule in self.resp_nested.items():
            if isinstance(rule, dict) and "field" in rule:
                out[int(rule["field"])] = name
        return out

    def schema_for_naming(self) -> dict[str, Any]:
        """اسکیمای نام‌دار کامل پاسخ، برای نام‌گذاری بازگشتی."""
        out: dict[str, Any] = dict(self.resp)
        out.update(self.resp_nested)
        return out


def _to_field_schema(named: dict[str, Any]) -> dict[int, Any]:
    """تبدیل اسکیمای نام‌دار به اسکیمای شماره‌محور برای decode.

    فیلدهای ساده (int) در خروجی نمی‌آیند چون برگ هستند و باید bytes بمانند.
    فیلدهای تودرتو با دیکشنری خالی {} علامت می‌خورند تا decode بداند
    آن‌ها را باز کند.
    """
    out: dict[int, Any] = {}
    for name, rule in named.items():
        if isinstance(rule, int):
            continue
        if isinstance(rule, dict) and "field" in rule:
            out[int(rule["field"])] = _to_field_schema(rule["fields"])
    return out


class RpcRegistry:
    """نگهدارنده RPC ها با پشتیبانی override."""

    def __init__(self) -> None:
        self._specs: dict[str, RpcSpec] = {}
        self._register_defaults()

    def register(self, spec: RpcSpec) -> None:
        self._specs[spec.full_name] = spec

    def get(self, full_name: str) -> RpcSpec:
        spec = self._specs.get(full_name)
        if spec is None:
            raise KeyError(
                f"RPC ناشناخته: {full_name}. "
                f"با registry.register() اضافه کن یا از registry.names() ببین."
            )
        return spec

    def names(self) -> list[str]:
        return sorted(self._specs)

    def by_service(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for name, spec in self._specs.items():
            out.setdefault(spec.service, []).append(spec.method)
        for methods in out.values():
            methods.sort()
        return out

    def load_overrides(self, data: dict[str, Any]) -> int:
        """اعمال override روی شماره فیلدها. برمی‌گرداند تعداد متد تغییرکرده."""
        changed = 0
        for full_name, patch in data.items():
            spec = self._specs.get(full_name)
            if spec is None:
                logger.warning("override برای RPC ناشناخته: %s", full_name)
                continue
            if "req" in patch:
                spec.req.update(patch["req"])
            if "resp" in patch:
                spec.resp.update(patch["resp"])
            changed += 1
        return changed

    def load_schema_file(self, path: str | Path) -> int:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return self.load_overrides(data)

    def _register_defaults(self) -> None:
        for spec in _DEFAULT_SPECS:
            self.register(copy.deepcopy(spec))


# ---------- ساخت درخواست ----------
def encode_request(spec: RpcSpec, args: dict[str, Any]) -> bytes:
    """ساخت payload از آرگومان‌های نام‌دار با نقشه فیلد spec."""
    schema = spec.schema()
    known = set(schema)
    for key, val in args.items():
        if val is not None and key not in known:
            raise KeyError(
                f"فیلد '{key}' در {spec.full_name} تعریف نشده. "
                f"فیلدهای موجود: {sorted(known)}"
            )
    return encode_named(args, schema)


def decode_response(spec: RpcSpec, frame: bytes) -> dict[str, Any]:
    """رمزگشایی پاسخ به دیکشنری با نام فیلدها (بازگشتی).

    فیلدهای تودرتو هم نام‌گذاری می‌شوند، تا کلاینت با کلیدهای خوانا
    کار کند: {"messages": [{"rid": 1, "message": {"textMessage": ...}}]}
    """
    raw = decode(frame, spec.resp_schema())
    return _name_dict(raw, spec.schema_for_naming())


def _name_dict(raw: dict[int, list[Any]], named: dict[str, Any]) -> dict[str, Any]:
    """تبدیل {شماره: [مقادیر]} به {نام: مقدار}، بازگشتی.

    `named` اسکیمای نام‌دار است: {"rid": 1, "message": {"field": 5, "fields": {...}}}
    """
    names: dict[int, str] = {}
    subs: dict[int, dict[str, Any]] = {}
    for name, rule in named.items():
        if isinstance(rule, int):
            names[rule] = name
        elif isinstance(rule, dict) and "field" in rule:
            num = int(rule["field"])
            names[num] = name
            subs[num] = rule["fields"]

    out: dict[str, Any] = {}
    for num, values in raw.items():
        name = names.get(num, f"field_{num}")
        sub = subs.get(num)
        converted: list[Any] = []
        for value in values:
            if sub is not None and isinstance(value, dict):
                converted.append(_name_dict(value, sub))
            else:
                converted.append(value)
        out[name] = converted[0] if len(converted) == 1 else converted
    return out


# ---------- Peer ----------
PEER_TYPE = {"user": 1, "chat": 2, "group": 3, "channel": 4}


def make_peer(peer_type: str | int, peer_id: int, access_hash: int = 0) -> dict[str, Any]:
    """ساخت ساختار Peer برای ارسال به بله."""
    if isinstance(peer_type, str):
        try:
            peer_type = PEER_TYPE[peer_type]
        except KeyError:
            raise ValueError(f"نوع peer ناشناخته: {peer_type}")
    return {"type": peer_type, "id": peer_id, "accessHash": access_hash}


# ---------- اسکیماهای تودرتو ----------
PEER_SCHEMA: dict[str, Any] = {
    "field": 1,
    "fields": {"type": 1, "id": 2, "accessHash": 3},
}
TEXT_MESSAGE_SCHEMA: dict[str, Any] = {
    "field": 1,
    "fields": {"text": 1},
}
MESSAGE_BODY_SCHEMA: dict[str, Any] = {
    "field": 3,
    "fields": {"textMessage": TEXT_MESSAGE_SCHEMA},
}

# ردیف پیام در تاریخچه و در پاسخ‌ها
MESSAGE_ROW_SCHEMA: dict[str, Any] = {
    "field": 1,
    "fields": {
        "rid": 1,
        "date": 2,
        "senderId": 3,
        "isOut": 4,
        "message": {"field": 5, "fields": {"textMessage": TEXT_MESSAGE_SCHEMA}},
    },
}

USER_SCHEMA: dict[str, Any] = {
    "field": 1,
    "fields": {"id": 1, "name": 2, "username": 3},
}

DIALOG_SCHEMA: dict[str, Any] = {
    "field": 1,
    "fields": {
        "peer": PEER_SCHEMA,
        "unreadCount": 2,
        "lastMessage": 3,
        "lastDate": 4,
        "pinned": 5,
        "title": 6,
    },
}

_PEER = {"peer": PEER_SCHEMA}
_RID = {"rid": 2}


# ---------- جدول پیش‌فرض ----------
# شماره فیلدها best-effort است و از ساختارهای مستندشده (peer, rid,
# textMessage.text, LoadHistoryRequest) و الگوی رایج gRPC بله گرفته شده.
# هر کدام را می‌توان با override عوض کرد.
_DEFAULT_SPECS: list[RpcSpec] = [
    # ===== Messaging =====
    RpcSpec("messaging", "messaging", "SendMessage",
            req={**_PEER, **_RID, "isSilent": 4, "replyTo": 5},
            nested={"message": MESSAGE_BODY_SCHEMA},
            resp={"rid": 1, "date": 2, "seq": 3},
            doc="ارسال پیام متنی/مدیا به یک peer", needs_peer=True),
    RpcSpec("messaging", "messaging", "EditMessage",
            req={**_PEER, "rid": 2},
            nested={"message": MESSAGE_BODY_SCHEMA},
            resp={"rid": 1, "date": 2}, doc="ویرایش پیام", needs_peer=True),
    RpcSpec("messaging", "messaging", "DeleteMessage",
            req={**_PEER, "rids": 2, "revoke": 3, "justMine": 4},
            resp={"deleted": 1}, doc="حذف پیام", dangerous=True, needs_peer=True),
    RpcSpec("messaging", "messaging", "LoadHistory",
            req={**_PEER, "date": 2, "loadMode": 3, "limit": 4},
            resp={"messages": 1, "hasMore": 2, "lastDate": 3},
            resp_nested={
                "messages": {"field": 1, "fields": MESSAGE_ROW_SCHEMA["fields"]},
            },
            doc="خواندن تاریخچه پیام‌ها", needs_peer=True),
    RpcSpec("messaging", "messaging", "ReadMessage",
            req={**_PEER, "date": 2}, resp={"ok": 1},
            doc="علامت‌گذاری خوانده‌شده", needs_peer=True),
    RpcSpec("messaging", "messaging", "ForwardMessage",
            req={"to": PEER_SCHEMA, "from": PEER_SCHEMA, "rids": 3, "dates": 4},
            resp={"rids": 1}, doc="فوروارد پیام"),
    RpcSpec("messaging", "messaging", "SendTyping",
            req={**_PEER, "typing": 2}, resp={"ok": 1},
            doc="نمایش «در حال تایپ»", needs_peer=True),
    RpcSpec("messaging", "messaging", "MessageSearch",
            req={**_PEER, "query": 2, "limit": 3},
            resp={"messages": 1}, doc="جستجوی متن در یک گفتگو", needs_peer=True),
    RpcSpec("messaging", "messaging", "PinMessage",
            req={**_PEER, "rid": 2, "date": 3}, resp={"ok": 1},
            doc="سنجاق پیام", needs_peer=True),
    RpcSpec("messaging", "messaging", "UnpinMessage",
            req={**_PEER}, resp={"ok": 1}, doc="برداشتن سنجاق", needs_peer=True),

    # ===== Reactions =====
    RpcSpec("reactions", "reactions", "AddReaction",
            req={**_PEER, "rid": 2, "date": 3, "code": 4},
            resp={"ok": 1}, doc="افزودن واکنش", needs_peer=True),
    RpcSpec("reactions", "reactions", "RemoveReaction",
            req={**_PEER, "rid": 2, "date": 3}, resp={"ok": 1},
            doc="حذف واکنش", needs_peer=True),
    RpcSpec("reactions", "reactions", "ListReactions",
            req={**_PEER, "rid": 2, "date": 3},
            resp={"reactions": 1}, doc="لیست واکنش‌های یک پیام", needs_peer=True),

    # ===== Dialogs / Chats =====
    RpcSpec("messaging", "messaging", "LoadDialogs",
            req={"limit": 1, "offset": 2, "excludePinned": 3},
            resp={"dialogs": 1, "hasMore": 2},
            resp_nested={
                "dialogs": {"field": 1, "fields": DIALOG_SCHEMA["fields"]},
            },
            doc="لیست گفتگوها"),
    RpcSpec("messaging", "messaging", "LoadChats",
            req={"limit": 1, "offset": 2}, resp={"chats": 1},
            doc="لیست گروه‌ها و کانال‌ها"),
    RpcSpec("messaging", "messaging", "CreateGroup",
            req={"title": 1, "users": 2}, resp={"peer": 1},
            doc="ساخت گروه"),
    RpcSpec("messaging", "messaging", "AddGroupMember",
            req={**_PEER, "users": 2}, resp={"ok": 1},
            doc="افزودن عضو به گروه", needs_peer=True),
    RpcSpec("messaging", "messaging", "RemoveGroupMember",
            req={**_PEER, "users": 2}, resp={"ok": 1},
            doc="حذف عضو از گروه", dangerous=True, needs_peer=True),
    RpcSpec("messaging", "messaging", "LeaveGroup",
            req={**_PEER}, resp={"ok": 1},
            doc="خروج از گروه", dangerous=True, needs_peer=True),
    RpcSpec("messaging", "messaging", "JoinChannel",
            req={**_PEER}, resp={"ok": 1}, doc="عضویت در کانال", needs_peer=True),
    RpcSpec("messaging", "messaging", "LeaveChannel",
            req={**_PEER}, resp={"ok": 1},
            doc="خروج از کانال", dangerous=True, needs_peer=True),
    RpcSpec("messaging", "messaging", "GetChatInfo",
            req={**_PEER}, resp={"chat": 1}, doc="اطلاعات گفتگو", needs_peer=True),
    RpcSpec("messaging", "messaging", "EditChatTitle",
            req={**_PEER, "title": 2}, resp={"ok": 1},
            doc="تغییر نام گروه/کانال", needs_peer=True),
    RpcSpec("messaging", "messaging", "SetChatPhoto",
            req={**_PEER, "photo": 2}, resp={"ok": 1},
            doc="تغییر عکس گروه/کانال", needs_peer=True),
    RpcSpec("messaging", "messaging", "MuteChat",
            req={**_PEER, "until": 2}, resp={"ok": 1},
            doc="بی‌صدا کردن گفتگو", needs_peer=True),
    RpcSpec("messaging", "messaging", "ArchiveChat",
            req={**_PEER, "archive": 2}, resp={"ok": 1},
            doc="آرشیو کردن گفتگو", needs_peer=True),
    RpcSpec("messaging", "messaging", "ClearHistory",
            req={**_PEER}, resp={"ok": 1},
            doc="پاک کردن تاریخچه", dangerous=True, needs_peer=True),

    # ===== Contacts =====
    RpcSpec("contacts", "contacts", "LoadContacts",
            req={"limit": 1, "offset": 2}, resp={"users": 1},
            doc="لیست مخاطبین"),
    RpcSpec("contacts", "contacts", "AddContact",
            req={"user": 1, "firstName": 2, "lastName": 3},
            resp={"ok": 1}, doc="افزودن مخاطب"),
    RpcSpec("contacts", "contacts", "RemoveContact",
            req={"user": 1}, resp={"ok": 1},
            doc="حذف مخاطب", dangerous=True),
    RpcSpec("contacts", "contacts", "SearchContacts",
            req={"query": 1, "limit": 2}, resp={"users": 1},
            doc="جستجوی مخاطب"),
    RpcSpec("contacts", "contacts", "BlockUser",
            req={"user": 1}, resp={"ok": 1}, doc="بلاک کردن کاربر"),
    RpcSpec("contacts", "contacts", "UnblockUser",
            req={"user": 1}, resp={"ok": 1}, doc="آنبلاک کردن کاربر"),

    # ===== Presence =====
    RpcSpec("presence", "presence", "SetOnline",
            req={"online": 1}, resp={"ok": 1}, doc="تنظیم وضعیت آنلاین"),
    RpcSpec("presence", "presence", "GetPresence",
            req={"user": 1}, resp={"online": 1, "lastSeen": 2},
            doc="وضعیت آنلاین یک کاربر"),
    RpcSpec("presence", "presence", "SubscribePresence",
            req={"user": 1}, resp={"ok": 1},
            doc="اشتراک در تغییر وضعیت کاربر"),

    # ===== Profile =====
    RpcSpec("users", "users", "GetMe",
            req={}, resp={"user": 1},
            resp_nested={"user": USER_SCHEMA},
            doc="اطلاعات اکانت خودت"),
    RpcSpec("users", "users", "GetUser",
            req={"user": 1}, resp={"user": 1},
            resp_nested={"user": USER_SCHEMA},
            doc="اطلاعات یک کاربر"),
    RpcSpec("users", "users", "EditProfile",
            req={"name": 1, "username": 2, "about": 3},
            resp={"ok": 1}, doc="ویرایش پروفایل"),
    RpcSpec("users", "users", "SetProfilePhoto",
            req={"photo": 1}, resp={"ok": 1}, doc="تغییر عکس پروفایل"),
    RpcSpec("users", "users", "ResolveUsername",
            req={"username": 1}, resp={"peer": 1},
            resp_nested={"peer": PEER_SCHEMA},
            doc="تبدیل یوزرنیم به peer"),

    # ===== Files =====
    RpcSpec("files", "files", "UploadFile",
            req={"name": 1, "size": 2, "mimeType": 3, "chunk": 4, "offset": 5},
            resp={"fileId": 1, "accessHash": 2}, doc="آپلود فایل"),
    RpcSpec("files", "files", "DownloadFile",
            req={"fileId": 1, "accessHash": 2, "offset": 3, "limit": 4},
            resp={"chunk": 1, "total": 2}, doc="دانلود فایل"),
    RpcSpec("files", "files", "GetFileInfo",
            req={"fileId": 1}, resp={"name": 1, "size": 2, "mimeType": 3},
            doc="اطلاعات فایل"),

    # ===== Wallet =====
    RpcSpec("wallet", "wallet", "GetWallet",
            req={}, resp={"balance": 1, "currency": 2}, doc="موجودی کیف پول"),
    RpcSpec("wallet", "wallet", "TransferMoney",
            req={"to": PEER_SCHEMA, "amount": 2, "description": 3},
            resp={"ok": 1, "txId": 2},
            doc="انتقال پول", dangerous=True),
    RpcSpec("wallet", "wallet", "GetTransactions",
            req={"limit": 1, "offset": 2}, resp={"transactions": 1},
            doc="تاریخچه تراکنش‌ها"),
    RpcSpec("wallet", "wallet", "GetPaymentRequest",
            req={"id": 1}, resp={"amount": 1, "status": 2},
            doc="اطلاعات درخواست پرداخت"),

    # ===== Bots =====
    RpcSpec("bots", "bots", "StartBot",
            req={"bot": 1}, resp={"ok": 1}, doc="شروع گفتگو با ربات"),
    RpcSpec("bots", "bots", "GetBotInfo",
            req={"bot": 1}, resp={"bot": 1}, doc="اطلاعات ربات"),
    RpcSpec("bots", "bots", "SetBotCommands",
            req={"bot": 1, "commands": 2}, resp={"ok": 1},
            doc="تنظیم دستورات ربات"),

    # ===== Search =====
    RpcSpec("search", "search", "GlobalSearch",
            req={"query": 1, "limit": 2, "type": 3},
            resp={"results": 1}, doc="جستجوی سراسری"),
    RpcSpec("search", "search", "SearchUsers",
            req={"query": 1, "limit": 2}, resp={"users": 1},
            doc="جستجوی کاربر"),

    # ===== Stickers =====
    RpcSpec("stickers", "stickers", "LoadStickerSets",
            req={"limit": 1}, resp={"sets": 1}, doc="لیست پک‌های استیکر"),
    RpcSpec("stickers", "stickers", "SendSticker",
            req={**_PEER, **_RID, "sticker": 3}, resp={"rid": 1},
            doc="ارسال استیکر", needs_peer=True),

    # ===== Settings =====
    RpcSpec("settings", "settings", "GetSettings",
            req={}, resp={"settings": 1}, doc="تنظیمات اکانت"),
    RpcSpec("settings", "settings", "UpdateSettings",
            req={"settings": 1}, resp={"ok": 1}, doc="به‌روزرسانی تنظیمات"),
    RpcSpec("settings", "settings", "Logout",
            req={}, resp={"ok": 1},
            doc="خروج از اکانت (session باطل می‌شود)", dangerous=True),
]

# ---------- نمونه singleton ----------
registry = RpcRegistry()

# بارگذاری override از env اگر تنظیم شده باشد
_schema_path = os.environ.get("BADKING_RPC_SCHEMA")
if _schema_path and Path(_schema_path).exists():
    try:
        _n = registry.load_schema_file(_schema_path)
        logger.info("schema override بارگذاری شد: %d متد", _n)
    except Exception as exc:  # pragma: no cover
        logger.warning("بارگذاری schema override شکست خورد: %s", exc)
