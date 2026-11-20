"""تست BaleMethod — لایه سازگاری متد سفارشی aiobale."""

from __future__ import annotations

import asyncio

import pytest

from badking import BaleMethod


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class SendInlineCallback(BaleMethod):
    __service__ = "bale.ketf.v1.Ketf"
    __method__ = "SendInlineCallback"

    peer: dict
    message_id: dict
    data: dict


def test_fields_extracted():
    assert SendInlineCallback.fields() == {
        1: "peer",
        2: "message_id",
        3: "data",
    }


def test_call_uses_raw_call():
    calls = []

    class FakeClient:
        async def raw_call(self, name, fields):
            calls.append((name, fields))
            return {"ok": 1}

    result = run(
        SendInlineCallback.call(
            FakeClient(), peer={"id": 1}, message_id={"id": 2}, data={"x": 3}
        )
    )
    assert result == {"ok": 1}
    assert calls[0][0] == "bale.ketf.v1.Ketf.SendInlineCallback"
    assert calls[0][1] == {
        1: {"id": 1},
        2: {"id": 2},
        3: {"x": 3},
    }


def test_call_rejects_unknown_field():
    class FakeClient:
        async def raw_call(self, name, fields):
            return {}

    with pytest.raises(KeyError) as info:
        run(SendInlineCallback.call(FakeClient(), unknown=1))
    assert "تعریف نشده" in str(info.value)


def test_call_requires_raw_call():
    class NoRawCall:
        pass

    with pytest.raises(TypeError) as info:
        run(SendInlineCallback.call(NoRawCall()))
    assert "raw_call" in str(info.value)


def test_numeric_field_keys_accepted():
    calls = []

    class FakeClient:
        async def raw_call(self, name, fields):
            calls.append(fields)
            return {}

    run(SendInlineCallback.call(FakeClient(), **{"1": {"id": 9}}))
    assert calls[0] == {1: {"id": 9}}


def test_exported_from_badking():
    import badking

    assert hasattr(badking, "BaleMethod")
