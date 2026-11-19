"""تستهای فاز ۶: Connector، Scheduler، JobQueue، EventBus، ORM، Voice/OCR."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking.connectors import Auth, Connector  # noqa: E402
from badking.events import EventBus  # noqa: E402
from badking.jobs import JobQueue, Scheduler  # noqa: E402
from badking.media import OCR, Voice  # noqa: E402
from badking.orm import Store  # noqa: E402


@pytest.mark.asyncio
async def test_connector_auth_and_retry():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.headers.get("Authorization"), request.url.path))
        if len(calls) == 1:
            return httpx.Response(500, json={"error": "temp"})
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conn = Connector(base_url="https://api.example.com", auth=Auth(type="bearer", token="T"),
                     retries=3, backoff=0.01, client=client)
    result = await conn.post("/pay", json_body={"x": 1})
    assert result.status_code == 200
    assert result.attempts == 2
    assert calls[0][0] == "Bearer T"
    await conn.close()


@pytest.mark.asyncio
async def test_connector_webhook_signature():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["sig"] = request.headers.get("X-Badking-Signature")
        return httpx.Response(200, json={"ok": True})

    conn = Connector(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    await conn.send_webhook("https://hook.example.com", {"a": 1}, secret="s3cr3t")
    assert seen["sig"] and len(seen["sig"]) == 64
    await conn.close()


@pytest.mark.asyncio
async def test_scheduler_one_shot():
    fired = []

    async def job(name):
        fired.append(name)

    s = Scheduler()
    s.schedule(job, delay=0.01, name="report")
    await s.start()

    # انتظار شرطی، نه ثابت زمانی: در مجموعه شلوغ، ۰.۱ ثانیه کافی نیست.
    for _ in range(100):
        if fired:
            break
        await asyncio.sleep(0.02)

    await s.stop()
    assert fired == ["report"]


@pytest.mark.asyncio
async def test_job_queue():
    done = []

    async def work(x):
        done.append(x)

    q = JobQueue(workers=2)
    await q.start()
    for i in range(5):
        await q.submit(work, i)
    await q.join()
    await q.stop()
    assert sorted(done) == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_event_bus():
    bus = EventBus()
    got = []

    @bus.on("payment")
    async def on_payment(amount):
        got.append(amount)

    await bus.emit("payment", amount=1000)
    assert got == [1000]


def test_orm_store(tmp_path):
    store = Store(str(tmp_path / "data.db"))
    store.put("u1", {"name": "علی", "score": 10}, kind="user")
    assert store.get("u1")["name"] == "علی"
    assert len(store.find(kind="user")) == 1
    store.delete("u1")
    assert store.get("u1") is None


@pytest.mark.asyncio
async def test_voice_ocr_callbacks():
    async def stt(audio: bytes) -> str:
        return "متن تبدیلشده"

    async def ocr(image: bytes) -> str:
        return "متن عکس"

    async def tts(text: str) -> bytes:
        return b"audio"

    voice = Voice(stt_func=stt, tts_func=tts)
    assert await voice.to_text(b"x") == "متن تبدیلشده"
    assert await voice.to_speech("سلام") == b"audio"
    assert await OCR(func=ocr).read(b"img") == "متن عکس"
