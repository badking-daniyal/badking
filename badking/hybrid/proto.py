"""کدک Protobuf از صفر — بدون فایل .proto و بدون کتابخانه تولید کد.

پروتکل داخلی بله بسته است و .proto رسمی ندارد. این ماژول یک کدک عمومی
protobuf است که با آن می‌توان هر پیامی را ساخت و خواند، فقط با دانستن
شماره فیلدها.

انواع wire:
    0 = varint      (int، bool، enum)
    1 = 64-bit      (fixed64، double)
    2 = length-delimited (string، bytes، پیام تودرتو)
    5 = 32-bit      (fixed32، float)

نکته طراحی مهم: رمزگشایی **اسکیما-محور** است. بدون اسکیما هیچ فیلدی
تودرتو تفسیر نمی‌شود، چون حدس زدن باعث می‌شود متن‌هایی مثل "hi" که
بایت‌هایشان تصادفاً شبیه protobuf است، خراب شوند.
"""

from __future__ import annotations

import struct
from typing import Any, Iterable


class ProtoError(Exception):
    """خطای رمزگشایی protobuf."""


# ---------- نوشتن ----------
def write_varint(value: int) -> bytes:
    """کدگذاری varint بدون علامت."""
    if value < 0:
        value &= (1 << 64) - 1  # two's complement برای منفی
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def read_varint(data: bytes, pos: int = 0) -> tuple[int, int]:
    """خواندن varint. برمی‌گرداند (مقدار، موقعیت بعدی)."""
    result = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise ProtoError("varint ناتمام")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 63:
            raise ProtoError("varint بیش از حد بلند")


def _tag(field: int, wire: int) -> bytes:
    return write_varint((field << 3) | wire)


def enc_varint(field: int, value: int) -> bytes:
    return _tag(field, 0) + write_varint(value)


def enc_bool(field: int, value: bool) -> bytes:
    return enc_varint(field, 1 if value else 0)


def enc_bytes(field: int, value: bytes) -> bytes:
    return _tag(field, 2) + write_varint(len(value)) + value


def enc_string(field: int, value: str) -> bytes:
    return enc_bytes(field, value.encode("utf-8"))


def enc_message(field: int, body: bytes) -> bytes:
    return enc_bytes(field, body)


def enc_double(field: int, value: float) -> bytes:
    return _tag(field, 1) + struct.pack("<d", value)


def enc_float(field: int, value: float) -> bytes:
    return _tag(field, 5) + struct.pack("<f", value)


def enc_fixed64(field: int, value: int) -> bytes:
    return _tag(field, 1) + struct.pack("<Q", value)


def enc_fixed32(field: int, value: int) -> bytes:
    return _tag(field, 5) + struct.pack("<I", value)


# ---------- خواندن ----------
def decode(data: bytes, schema: dict[int, Any] | None = None) -> dict[int, list[Any]]:
    """رمزگشایی یک پیام به دیکشنری {شماره فیلد: [مقادیر]}.

    اگر `schema` بدهی ({شماره فیلد: زیراسکیما})، فقط فیلدهای اعلام‌شده
    به‌صورت تودرتو رمزگشایی می‌شوند و بقیه bytes می‌مانند.

    بدون schema، هیچ فیلدی تودرتو تفسیر نمی‌شود.
    """
    out: dict[int, list[Any]] = {}
    pos = 0
    while pos < len(data):
        key, pos = read_varint(data, pos)
        field = key >> 3
        wire = key & 0x07
        if field == 0:
            raise ProtoError("شماره فیلد صفر مجاز نیست")
        if wire == 0:
            value, pos = read_varint(data, pos)
        elif wire == 1:
            if pos + 8 > len(data):
                raise ProtoError("fixed64 ناتمام")
            value = struct.unpack("<Q", data[pos:pos + 8])[0]
            pos += 8
        elif wire == 2:
            length, pos = read_varint(data, pos)
            if pos + length > len(data):
                raise ProtoError("length-delimited ناتمام")
            raw = data[pos:pos + length]
            pos += length
            sub = schema.get(field) if schema else None
            value = decode(raw, sub) if isinstance(sub, dict) else raw
        elif wire == 5:
            if pos + 4 > len(data):
                raise ProtoError("fixed32 ناتمام")
            value = struct.unpack("<I", data[pos:pos + 4])[0]
            pos += 4
        else:
            raise ProtoError(f"wire type پشتیبانی‌نشده: {wire}")
        out.setdefault(field, []).append(value)
    return out


def encode_named(value: dict[str, Any], schema: dict[str, Any]) -> bytes:
    """کدگذاری دیکشنری نام‌دار با اسکیمای {نام: شماره فیلد}.

    سه شکل قاعده پشتیبانی می‌شود:

        "peer": 1                              → فیلد ساده
        "peer": {"field": 1, "fields": {...}}  → پیام تودرتو
        "users": {"field": 3, "fields": {...}, "repeated": True}  → لیست پیام

    تودرتویی هر عمقی مجاز است: MessageContent{15: TextMessage{1: value}}.

        schema = {
            "peer": {"field": 1, "fields": {"type": 1, "id": 2, "accessHash": 3}},
            "content": {"field": 3, "fields": {
                "text": {"field": 15, "fields": {"value": 1}},
            }},
        }
        encode_named({"peer": {"type": 1, "id": 7},
                      "content": {"text": {"value": "hi"}}}, schema)
    """
    fields: dict[int, Any] = {}
    for name, val in value.items():
        if val is None:
            continue
        rule = schema.get(name)
        if rule is None:
            raise ProtoError(f"فیلد '{name}' در اسکیما نیست: {sorted(schema)}")

        if isinstance(rule, int):
            fields[rule] = val
            continue

        if not isinstance(rule, dict) or "field" not in rule:
            raise ProtoError(f"اسکیمای نامعتبر برای '{name}': {rule!r}")

        num = int(rule["field"])
        sub = rule.get("fields")

        if sub is None:
            # پیام تودرتو بدون اسکیمای اعلام‌شده: dict با کلید عددی
            fields[num] = val
            continue

        items = val if isinstance(val, list) else [val]
        encoded: list[bytes] = []
        for item in items:
            if isinstance(item, bytes):
                encoded.append(item)
            elif isinstance(item, dict):
                encoded.append(encode_named(item, sub))
            else:
                raise ProtoError(
                    f"فیلد '{name}' باید dict یا لیست dict باشد، نه {type(item).__name__}"
                )
        fields[num] = encoded if isinstance(val, list) else encoded[0]

    return build(fields)


def to_bytes(value: Any) -> bytes:
    """تبدیل مقدار پایتونی به bytes برای فیلد length-delimited."""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, dict):
        if not all(isinstance(k, int) for k in value):
            raise ProtoError(
                "دیکشنری با کلید نام‌دار را نمی‌توان مستقیم کدگذاری کرد؛ "
                "از encode_named() استفاده کن یا bytes بده."
            )
        return build(value)
    raise ProtoError(f"نوع پشتیبانی‌نشده: {type(value).__name__}")


def build(fields: dict[int, Any]) -> bytes:
    """ساخت پیام از دیکشنری ساده.

    value می‌تواند: int، bool، str، bytes، dict (با کلید عددی)، یا لیست.
    """
    out = bytearray()
    for field, value in fields.items():
        if value is None:
            continue
        values: Iterable[Any] = value if isinstance(value, list) else [value]
        for v in values:
            if v is None:
                continue
            if isinstance(v, bool):
                out += enc_bool(field, v)
            elif isinstance(v, int):
                out += enc_varint(field, v)
            elif isinstance(v, float):
                out += enc_double(field, v)
            elif isinstance(v, (str, bytes, dict)):
                out += enc_bytes(field, to_bytes(v))
            else:
                raise ProtoError(f"نوع پشتیبانی‌نشده در فیلد {field}: {type(v).__name__}")
    return bytes(out)


# ---------- کمک‌کننده‌های خواندن ----------
def get_int(msg: dict[int, list[Any]], field: int, default: int = 0) -> int:
    vals = msg.get(field)
    if not vals:
        return default
    v = vals[0]
    return v if isinstance(v, int) else default


def get_str(msg: dict[int, list[Any]], field: int, default: str = "") -> str:
    vals = msg.get(field)
    if not vals:
        return default
    v = vals[0]
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return default
    return v if isinstance(v, str) else default


def get_bytes(msg: dict[int, list[Any]], field: int, default: bytes = b"") -> bytes:
    vals = msg.get(field)
    if not vals:
        return default
    v = vals[0]
    if isinstance(v, bytes):
        return v
    if isinstance(v, str):
        return v.encode("utf-8")
    return default


def get_msg(msg: dict[int, list[Any]], field: int) -> dict[int, list[Any]] | None:
    vals = msg.get(field)
    if not vals:
        return None
    v = vals[0]
    return v if isinstance(v, dict) else None
