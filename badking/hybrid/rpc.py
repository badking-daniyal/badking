"""رجیستری RPC های self-bot — ۷۹ متد، اسکیمای واقعی.

بله صدها RPC داخلی دارد که هیچ‌کدام مستند رسمی نیستند. این ماژول یک
رجیستری قابل بازنویسی است: هر متد با نام، سرویس، و نقشه شماره فیلدهای
درخواست تعریف شده. اگر بله پروتکل را عوض کرد، فقط این جدول را عوض
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
from .schema import METHODS, NESTED, RESPONSES, SERVICES

logger = logging.getLogger("badking.hybrid.rpc")


# ---------- اسکیمای تایپ‌های تودرتو ----------

PEER_SCHEMA: dict[str, int] = NESTED["Peer"]
CHAT_SCHEMA: dict[str, int] = NESTED["Chat"]
SHORT_PEER_SCHEMA: dict[str, int] = NESTED["ShortPeer"]
TEXT_MESSAGE_SCHEMA: dict[str, int] = NESTED["TextMessage"]
MESSAGE_CAPTION_SCHEMA: dict[str, int] = NESTED["MessageCaption"]
DOCUMENT_SCHEMA: dict[str, int] = NESTED["DocumentMessage"]
MESSAGE_CONTENT_SCHEMA: dict[str, int] = NESTED["MessageContent"]
TEMPLATE_MESSAGE_SCHEMA: dict[str, int] = NESTED["TemplateMessage"]
INLINE_KEYBOARD_SCHEMA: dict[str, int] = NESTED["InlineKeyboard"]
OTHER_MESSAGE_SCHEMA: dict[str, int] = NESTED["OtherMessage"]
INFO_MESSAGE_SCHEMA: dict[str, int] = NESTED["InfoMessage"]
QUOTED_MESSAGE_SCHEMA: dict[str, int] = NESTED["QuotedMessage"]
MESSAGE_DATA_SCHEMA: dict[str, int] = NESTED["MessageData"]
PEER_DATA_SCHEMA: dict[str, int] = NESTED["PeerData"]
USER_SCHEMA: dict[str, int] = NESTED["User"]
GROUP_SCHEMA: dict[str, int] = NESTED["Group"]
MEMBER_SCHEMA: dict[str, int] = NESTED["Member"]
PERMISSIONS_SCHEMA: dict[str, int] = NESTED["Permissions"]
REACTION_SCHEMA: dict[str, int] = NESTED["Reaction"]
MESSAGE_REACTION_SCHEMA: dict[str, int] = NESTED["MessageReaction"]
WALLET_SCHEMA: dict[str, int] = NESTED["Wallet"]
FILE_INFO_SCHEMA: dict[str, int] = NESTED["FileInfo"]
FILE_UPLOAD_SCHEMA: dict[str, int] = NESTED["FileUploadInfo"]
GIFT_PACKET_SCHEMA: dict[str, int] = NESTED["GiftPacket"]
BAN_DATA_SCHEMA: dict[str, int] = NESTED["BanData"]
INFO_PEER_SCHEMA: dict[str, int] = NESTED["InfoPeer"]

# سازگاری با نسخه قبل
MESSAGE_BODY_SCHEMA = MESSAGE_CONTENT_SCHEMA
MESSAGE_ROW_SCHEMA = {"field": 1, "fields": MESSAGE_DATA_SCHEMA}
DIALOG_SCHEMA = {"field": 3, "fields": PEER_DATA_SCHEMA}

PEER_TYPE: dict[str, int] = {
    "user": 1,
    "chat": 2,
    "group": 3,
    "channel": 4,
    "bot": 4,
}

# نوع peer در ChatType (برای فیلد chat)
CHAT_TYPE: dict[str, int] = {
    "unknown": 0,
    "private": 1,
    "group": 2,
    "channel": 3,
    "bot": 4,
    "supergroup": 5,
}


def make_peer(peer_type: str | int, peer_id: int, access_hash: int = 0) -> dict[str, Any]:
    """ساخت دیکشنری Peer آماده برای ارسال."""
    if isinstance(peer_type, str):
        ptype = PEER_TYPE.get(peer_type.lower())
        if ptype is None:
            raise ValueError(
                f"نوع peer ناشناخته: {peer_type}. "
                f"یکی از {sorted(PEER_TYPE)} را بده."
            )
    else:
        ptype = int(peer_type)
    out: dict[str, Any] = {"type": ptype, "id": int(peer_id)}
    if access_hash:
        out["accessHash"] = int(access_hash)
    return out


def make_chat(chat_type: str | int, chat_id: int) -> dict[str, Any]:
    """ساخت دیکشنری Chat (فیلد ۶ در SendMessage).

    دو نگاشت را میپذیرد:
    - ``CHAT_TYPE`` (private/group/channel/...) — نامهای استاندارد Chat.
    - ``PEER_TYPE`` (user/chat/group/channel) — چون ``Peer.type`` همین
     .names را دارد و ``send_message`` مستقیم آن را پاس میدهد.

    بدون این، ``make_chat("user", ...)`` و ``make_chat("chat", ...)``
    خطای ValueError میدادند و ارسال پیام به کاربر/چت ناممکن بود.
    """
    if isinstance(chat_type, str):
        key = chat_type.lower()
        ctype = CHAT_TYPE.get(key)
        if ctype is None:
            # Peer.type از PEER_TYPE میآید — آن را هم بپذیر
            ctype = PEER_TYPE.get(key)
        if ctype is None:
            raise ValueError(f"نوع chat ناشناخته: {chat_type}")
    else:
        ctype = int(chat_type)
    return {"type": ctype, "id": int(chat_id)}


def make_text_content(
    text: str,
    reply_markup: dict[str, Any] | None = None,
    temp_id: int | None = None,
) -> dict[str, Any]:
    """ساخت MessageContent متنی، با پشتیبانی اختیاری از inline keyboard.

    ساختار واقعی (aiobale 0.3.9، source-confirmed):
        MessageContent{15: TextMessage{1: value}}
    وقتی keyboard داده شود، متن داخل TemplateMessage قرار میگیرد:
        MessageContent{13: TemplateMessage{
            1: MessageContent{15: TextMessage{...}},
            2: tempId,
            5: InlineKeyboardMarkup{1: [Row{1: [Button]}]}
        }}

    ``reply_markup`` خروجی :func:`make_inline_keyboard` است.
    """
    content: dict[str, Any] = {"text": {"value": text}}
    if reply_markup is None:
        return content
    import time

    template: dict[str, Any] = {
        "message": content,
        "tempId": temp_id if temp_id is not None else int(time.time() * 1000),
    }
    # make_inline_keyboard کلید inlineKeyboardMarkup را برمیگرداند؛
    # اسکیمای TemplateMessage دقیقاً همان نام را میپذیرد.
    template.update(reply_markup)
    return {"botMessage": template}


def make_document_content(
    file_id: int,
    access_hash: int,
    name: str = "",
    mime_type: str = "",
    size: int | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    """MessageContent با فایل — فیلد ۴."""
    doc: dict[str, Any] = {
        "fileId": int(file_id),
        "accessHash": int(access_hash),
    }
    if name:
        doc["name"] = name
    if mime_type:
        doc["mimeType"] = mime_type
    if size is not None:
        doc["size"] = int(size)
    if caption:
        doc["caption"] = {"content": caption}
    return {"document": doc}


def make_inline_keyboard(rows: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """ساخت inline keyboard برای SelfBot (پروتکل داخلی بله).

    ورودی لیستی از ردیفها، هر ردیف لیستی از دکمهها. هر دکمه دیکشنری با
    کلیدهای دو شکل پذیرفته میشود:

      * نامهای دوستانه: ``text``، ``url``، ``callback_data``، ``copy_text``
      * نامهای اسکیما: ``text``، ``url``، ``callbackData``، ``copyText``

    شماره فیلدها از سورس رسمی aiobale 0.3.9 تأیید شدهاند
    (``types/inline_keyboard.py``):
        InlineKeyboardMarkup{1: [Row{1: [Button]}]}
        Button{1: text, 2: {1: url}, 3: {1: callback_data}, 9: {1: copy_text}}

    نکته پروتکلی: callback query در پروتکل داخلی SelfBot وجود ندارد
    (هیچ update type یا RPC مربوطهای در aiobale 0.3.9 نیست)، بنابراین
    ``callback_data`` تنها بهعنوان payload خروجی ارسال میشود و هیچ رویداد
    ``on_callback`` برای SelfBot وجود نخواهد داشت.
    """
    # سازگاری با نسخه قبلی: یک لیست تخت از دکمهها هم پذیرفته میشود
    # (مثلاً [{"text": "بلی"}] بهعنوان یک ردیف تکدکمهای).
    if rows and all(isinstance(item, dict) for item in rows):
        rows = [rows]  # type: ignore[list-item]

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            row = [row]
        buttons: list[dict[str, Any]] = []
        for button in row:
            if not isinstance(button, dict):
                raise TypeError(f"دکمه باید dict باشد، نه {type(button).__name__}")
            text = button.get("text")
            if not isinstance(text, str) or not text:
                raise ValueError("هر دکمه به متن 'text' غیرخالی نیاز دارد")
            item: dict[str, Any] = {"text": text}
            for src, dst in (
                ("url", "url"),
                ("callback_data", "callbackData"),
                ("callbackData", "callbackData"),
                ("copy_text", "copyText"),
                ("copyText", "copyText"),
            ):
                value = button.get(src)
                if value is not None:
                    item[dst] = {"value": str(value)}
            buttons.append(item)
        normalized_rows.append({"buttons": buttons})
    return {"inlineKeyboardMarkup": {"rows": normalized_rows}}


# ---------- مشخصات یک RPC ----------


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
        return f"{self.service.lower()}.{self.method}"

    @property
    def full_service(self) -> str:
        """نام کامل gRPC، مثل bale.messaging.v2.Messaging."""
        return SERVICES.get(self.service, self.service)

    def schema(self) -> dict[str, Any]:
        """اسکیمای کامل درخواست، با تودرتویی حل‌شده."""
        out: dict[str, Any] = {}
        for name, rule in self.req.items():
            out[name] = _resolve(rule)
        for name, rule in self.nested.items():
            out[name] = _resolve(rule)
        return out

    def resp_schema(self) -> dict[int, Any]:
        """اسکیمای پاسخ: {شماره فیلد: زیراسکیما}.

        هم resp و هم resp_nested را پوشش می‌دهد.
        """
        out: dict[int, Any] = {}
        for source in (self.resp, self.resp_nested):
            for name, rule in source.items():
                r = _resolve(rule)
                if isinstance(r, dict) and "fields" in r:
                    out[int(r["field"])] = _to_field_schema(r["fields"])
        return out

    def resp_names(self) -> dict[int, str]:
        """نقشه شماره فیلد → نام، شامل فیلدهای تودرتو."""
        out: dict[int, str] = {}
        for name, rule in self.resp.items():
            r = _resolve(rule)
            if isinstance(r, int):
                out[r] = name
        for name, rule in self.resp_nested.items():
            r = _resolve(rule)
            if isinstance(r, dict) and "field" in r:
                out[int(r["field"])] = name
        return out

    def schema_for_naming(self) -> dict[str, Any]:
        """اسکیمای نام‌دار کامل پاسخ، برای نام‌گذاری بازگشتی."""
        out: dict[str, Any] = {}
        for name, rule in self.resp.items():
            out[name] = _resolve(rule)
        for name, rule in self.resp_nested.items():
            out[name] = _resolve(rule)
        return out


def _resolve(rule: Any, seen: frozenset[str] = frozenset()) -> Any:
    """تبدیل قاعده فیلد به شکل قابل استفاده برای encode_named.

    قاعده می‌تواند باشد:
        عدد                                   → فیلد ساده
        {"field": N, "fields": "TypeName"}    → ارجاع به NESTED
        {"field": N, "fields": {...}}         → اسکیمای صریح

    پروتکل بله مرجع چرخشی دارد (MessageContent → TemplateMessage →
    MessageContent). با `seen` جلوی بازگشت بی‌نهایت گرفته می‌شود: بار
    دوم که به یک تایپ می‌رسیم، به‌عنوان فیلد خام (bytes) رد می‌شود.
    """
    if isinstance(rule, int):
        return rule

    if not isinstance(rule, dict) or "field" not in rule:
        raise ValueError(f"قاعده نامعتبر: {rule!r}")

    num = int(rule["field"])
    sub = rule.get("fields")

    if sub is None:
        return num

    if isinstance(sub, str):
        if sub in seen:
            # چرخه: به‌عنوان bytes خام رد می‌شود
            logger.debug("مرجع چرخشی در %s — به‌عنوان bytes رد شد", sub)
            return num
        nested = NESTED.get(sub)
        if nested is None:
            logger.debug("تایپ تودرتوی ناشناخته: %s", sub)
            return num
        inner_seen = seen | {sub}
        resolved = {k: _resolve(v, inner_seen) for k, v in nested.items()}
    else:
        resolved = {k: _resolve(v, seen) for k, v in sub.items()}

    out: dict[str, Any] = {"field": num, "fields": resolved}
    if rule.get("repeated"):
        out["repeated"] = True
    return out


def _to_field_schema(named: dict[str, Any]) -> dict[int, Any]:
    """تبدیل {نام: قاعده} به {شماره: زیراسکیما}، برای رمزگشایی."""
    out: dict[int, Any] = {}
    for name, rule in named.items():
        r = _resolve(rule)
        if isinstance(r, int):
            out[r] = None
        elif isinstance(r, dict) and "fields" in r:
            out[int(r["field"])] = _to_field_schema(r["fields"])
    return out


# ---------- رجیستری ----------


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

    def search(self, term: str) -> list[str]:
        """جستجوی متد با کلمه کلیدی در نام و توضیح."""
        t = term.lower()
        return [
            n
            for n, s in sorted(self._specs.items())
            if t in n.lower() or t in s.doc.lower()
        ]

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
        for service, method, req, doc, dangerous, needs_peer in METHODS:
            resp = RESPONSES.get(method, {})
            spec = RpcSpec(
                name=service.lower(),
                service=service,
                method=method,
                req=dict(req),
                resp=dict(resp),
                doc=doc,
                dangerous=dangerous,
                needs_peer=needs_peer,
            )
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
    """رمزگشایی پاسخ به دیکشنری با نام فیلدها (بازگشتی)."""
    raw = decode(frame, spec.resp_schema())
    return _name_dict(raw, spec.schema_for_naming())


def _name_dict(raw: dict[int, list[Any]], named: dict[str, Any]) -> dict[str, Any]:
    """تبدیل {شماره: [مقادیر]} به {نام: مقدار}، بازگشتی."""
    names: dict[int, str] = {}
    subs: dict[int, dict[str, Any]] = {}
    for name, rule in named.items():
        if isinstance(rule, int):
            names[rule] = name
        elif isinstance(rule, dict) and "field" in rule:
            names[int(rule["field"])] = name
            subs[int(rule["field"])] = rule.get("fields", {})

    out: dict[str, Any] = {}
    for num, values in raw.items():
        name = names.get(num, str(num))
        sub = subs.get(num)
        if sub and isinstance(values, list):
            conv = []
            for v in values:
                if isinstance(v, dict):
                    conv.append(_name_dict(v, sub))
                else:
                    conv.append(v)
            out[name] = conv if len(conv) != 1 else conv[0]
        else:
            out[name] = values[0] if len(values) == 1 else values
    return out


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
