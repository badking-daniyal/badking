"""Serialization Equivalence — تضمین میکند بهینهسازی صحت پروتکل را تغییر نداده.

پیادهسازی مرجع (نسخه قبل از بهینهسازی) را دوباره مینویسیم و خروجی
باینری `build()` بهینهشده را با آن در hundreds از ورودیهای تصادفی مقایسه میکنیم.
"""

from __future__ import annotations

import random
import struct

from badking.hybrid import proto


def ref_write_varint(value: int) -> bytes:
    if value < 0:
        value &= (1 << 64) - 1
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def ref_build(fields: dict) -> bytes:
    """پیادهسازی مرجع — دقیقاً همان کد قبل از بهینهسازی."""
    out = bytearray()
    for field, value in fields.items():
        if value is None:
            continue
        values = value if isinstance(value, list) else [value]
        for v in values:
            if v is None:
                continue
            tag = ref_write_varint((field << 3))
            if isinstance(v, bool):
                out += tag + ref_write_varint(1 if v else 0)
            elif isinstance(v, int):
                out += tag + ref_write_varint(v)
            elif isinstance(v, float):
                out += ref_write_varint((field << 3) | 1) + struct.pack("<d", v)
            elif isinstance(v, (str, bytes, dict)):
                raw = proto.to_bytes(v)
                out += ref_write_varint((field << 3) | 2) + ref_write_varint(len(raw)) + raw
            else:
                raise TypeError(type(v).__name__)
    return bytes(out)


class TestWriteVarintEquivalence:
    def test_same_bytes(self):
        values = [0, 1, 127, 128, 300, 2**31, 2**63 - 1, -1, -42, -2**40]
        for v in values:
            assert proto.write_varint(v) == ref_write_varint(v), v

    def test_random_values(self):
        rng = random.Random(42)
        for _ in range(500):
            v = rng.randint(-(2**63), 2**63 - 1)
            assert proto.write_varint(v) == ref_write_varint(v), v


class TestBuildEquivalence:
    def test_known_payloads(self):
        cases = [
            {1: 42},
            {1: 42, 2: "سلام"},
            {1: True, 2: False, 3: 0, 4: -5},
            {1: b"\x00\x01\x02", 2: {1: 7, 2: "x"}},
            {1: [1, 2, 3], 2: ["a", "b"]},
            {1: 3.14, 2: 0.0},
            {1: 300, 2: 2**40, 3: "تست طولانی" * 20},
        ]
        for case in cases:
            assert proto.build(case) == ref_build(case), case

    def test_random_payloads(self):
        rng = random.Random(7)
        for _ in range(200):
            fields = {}
            for i in range(1, rng.randint(2, 6)):
                kind = rng.choice(["int", "str", "bytes", "bool", "float", "nested"])
                if kind == "int":
                    fields[i] = rng.randint(-100000, 100000)
                elif kind == "str":
                    fields[i] = "".join(chr(rng.randint(32, 1300)) for _ in range(rng.randint(0, 10)))
                elif kind == "bytes":
                    fields[i] = bytes(rng.randint(0, 255) for _ in range(rng.randint(0, 8)))
                elif kind == "bool":
                    fields[i] = rng.choice([True, False])
                elif kind == "float":
                    fields[i] = rng.uniform(-1000, 1000)
                else:
                    fields[i] = {1: rng.randint(0, 100), 2: "nested"}
            assert proto.build(fields) == ref_build(fields), fields


class TestRoundtripAfterOptimization:
    def test_decode_matches(self):
        payload = proto.build({1: 42, 2: "سلام", 3: {1: 7}})
        decoded = proto.decode(payload, {1: int, 2: str, 3: {1: int}})
        assert proto.get_int(decoded, 1) == 42
        assert proto.get_str(decoded, 2) == "سلام"
