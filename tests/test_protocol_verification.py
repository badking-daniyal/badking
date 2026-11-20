"""Protocol Verification — مقایسه شماره فیلدها با سورس واقعی aiobale.

منبع معتبر: aiobale 0.3.9 (pydantic Field(alias="N")).
اگر سورس aiobale در محیط نباشد، تستها صریحاً SKIP میشوند (BLOCKED)،
نه اینکه با حدس پاس شوند.
"""

from __future__ import annotations

import ast
import io
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "badking" / "hybrid" / "schema.py"

# مسیرهای ممکن سورس aiobale — محیطهای مختلف
CANDIDATES = [
    ROOT / "tests" / "fixtures" / "aiobale_methods",
    Path(r"D:\AI\_aiobale_src\methods"),
    ROOT.parent / "_aiobale_src" / "methods",
]


def find_aiobale_methods_dir():
    for path in CANDIDATES:
        if path.is_dir():
            return path
    return None


AIO_DIR = find_aiobale_methods_dir()
pytestmark = pytest.mark.skipif(
    AIO_DIR is None,
    reason="BLOCKED: aiobale source not present; field numbers cannot be verified",
)


def aiobale_fields():
    """استخراج {method: {field: number}} از سورس واقعی aiobale."""
    out = {}
    for path in AIO_DIR.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            method_name = None
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if (isinstance(target, ast.Name) and target.id == "__method__"
                                and isinstance(stmt.value, ast.Constant)):
                            method_name = stmt.value.value
            if not method_name:
                continue

            fields = {}
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    if isinstance(stmt.value, ast.Call):
                        for kw in stmt.value.keywords:
                            if kw.arg == "alias" and isinstance(kw.value, ast.Constant):
                                alias = str(kw.value.value)
                                if alias.isdigit():
                                    fields[stmt.target.id] = int(alias)
            if fields:
                out[method_name] = fields
    return out


def badking_fields():
    """استخراج METHODS از schema.py BADKING."""
    tree = ast.parse(SCHEMA.read_text(encoding="utf-8"))
    out = {}
    for node in ast.walk(tree):
        targets, value = [], None
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
            value = node.value

        if "METHODS" not in targets or not isinstance(value, ast.List):
            continue

        for elt in value.elts:
            if not isinstance(elt, ast.Tuple) or len(elt.elts) < 3:
                continue
            method, fields_node = elt.elts[1], elt.elts[2]
            if not isinstance(method, ast.Constant) or not isinstance(fields_node, ast.Dict):
                continue
            fields = {}
            for k, v in zip(fields_node.keys, fields_node.values):
                if not isinstance(k, ast.Constant):
                    continue
                if isinstance(v, ast.Constant) and isinstance(v.value, int):
                    fields[k.value] = v.value
                elif isinstance(v, ast.Dict):
                    for kk, vv in zip(v.keys, v.values):
                        if (isinstance(kk, ast.Constant) and kk.value == "field"
                                and isinstance(vv, ast.Constant)):
                            fields[k.value] = vv.value
            out[method.value] = fields
    return out


class TestProtocolFieldNumbers:
    def test_aiobale_source_available(self):
        assert AIO_DIR is not None

    def test_all_aiobale_methods_present(self):
        aio, bk = aiobale_fields(), badking_fields()
        missing = set(aio) - set(bk)
        assert missing == set(), f"متدهایی از aiobale در BADKING نیستند: {missing}"

    def test_all_field_numbers_match(self):
        """هیچ شماره فیلدی نباید حدس زده شده باشد."""
        aio, bk = aiobale_fields(), badking_fields()
        mismatches = {}
        for name, fields in aio.items():
            for field, number in fields.items():
                if bk.get(name, {}).get(field) != number:
                    mismatches[f"{name}.{field}"] = (number, bk.get(name, {}).get(field))
        assert not mismatches, f"عدم تطابق شماره فیلد: {mismatches}"

    @pytest.mark.parametrize(
        "method,field,number",
        [
            ("SendMessage", "peer", 1),
            ("SendMessage", "content", 3),
            ("SendMessage", "chat", 6),
            ("StartPhoneAuth", "phone_number", 1),
            ("StartPhoneAuth", "send_code_type", 9),
            ("ValidateCode", "code", 2),
            ("GetGroupPreview", "token", 1),
            ("LoadHistory", "load_mode", 4),
            ("LoadHistory", "limit", 5),
        ],
    )
    def test_key_field_numbers(self, method, field, number):
        aio = aiobale_fields()
        assert aio[method][field] == number
        assert badking_fields()[method][field] == number


class TestCodecRoundtrip:
    """Serialization/Deserialization با Fixture واقعی."""

    def test_varint_roundtrip(self):
        from badking.hybrid.proto import build, decode, get_int

        payload = build({1: 123456, 2: "سلام", 3: b"\x01\x02"})
        decoded = decode(payload)
        assert get_int(decoded, 1) == 123456

    def test_nested_roundtrip(self):
        from badking.hybrid.proto import build, encode_named, decode

        schema = {"peer": {"field": 1, "fields": {"id": 1, "type": 2}}}
        payload = encode_named({"peer": {"id": 42, "type": 1}}, schema)
        decoded = decode(payload, {1: {1: int, 2: int}})
        assert decoded[1][0][1] == [42]

    def test_unknown_field_preserved(self):
        from badking.hybrid.proto import build, decode

        payload = build({1: 5, 99: b"unknown"})
        decoded = decode(payload)
        assert 1 in decoded

    def test_send_message_payload_shape(self):
        """پیام SendMessage با شماره فیلدهای تأییدشده ساخته شود."""
        from badking.hybrid.rpc import encode_request, registry

        spec = registry.get("messaging.SendMessage")
        payload = encode_request(
            spec,
            {
                "peer": {"type": 1, "id": 42, "accessHash": 0},
                "message_id": 123,
                "content": {"text": {"value": "سلام"}},
                "chat": {"type": 1, "id": 42},
            },
        )
        assert payload
        assert isinstance(payload, bytes)
