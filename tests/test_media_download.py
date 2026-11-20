"""تستهای دانلود رسانه SelfBot — کاملاً آفلاین (Mock)، بدون حساب واقعی.

شماره فیلدهای FileURL/FileInfo در ``test_protocol_fields_media`` از سورس رسمی
aiobale 0.3.9 تأیید شدهاند (raw.githubusercontent.com/aminmadaniofficial/aiobale/v0.3.9).
"""

from __future__ import annotations

import pytest

from badking.hybrid.download import (
    DownloadError,
    filename_from_url,
    resolve_destination,
    sanitize_filename,
    write_stream_atomic,
)
from badking.hybrid.schema import NESTED, RESPONSES, METHODS


# ---------- پروتکل (شماره فیلدها) ----------

def test_protocol_fields_media():
    """شماره فیلدها دقیقاً مطابق aiobale 0.3.9 (منبع رسمی)."""
    assert NESTED["FileURL"] == {
        "fileId": 1, "url": 2, "timeout": 3, "chunkSize": 7,
    }
    assert NESTED["FileInfo"]["fileId"] == 1
    assert NESTED["FileInfo"]["accessHash"] == 2
    assert NESTED["FileInfo"]["fileStorageVersion"]["field"] == 3
    assert RESPONSES["GetNasimFileUrl"]["file_urls"]["field"] == 1
    method = [m for m in METHODS if m[1] == "GetNasimFileUrl"]
    assert len(method) == 1
    assert method[0][2] == {"file": {"field": 1, "fields": "FileInfo"}}


def test_decode_file_url_response_uses_correct_fields():
    """پاسخ نمونه با فیلدهای aiobale به درستی دیکود میشود."""
    from badking.hybrid.proto import encode_named
    from badking.hybrid.rpc import registry, decode_response

    spec = registry.get("files.GetNasimFileUrl")
    inner = encode_named(
        {"fileId": 123, "url": "https://cdn.bale.ai/f/abc", "timeout": 60000, "chunkSize": 65536},
        {"fileId": 1, "url": 2, "timeout": 3, "chunkSize": 7},
    )
    frame = encode_named({"file_urls": inner}, spec.schema_for_naming())
    result = decode_response(spec, frame)
    urls = result["file_urls"]
    row = urls[0] if isinstance(urls, list) else urls
    assert row["url"] == b"https://cdn.bale.ai/f/abc"
    assert row["chunkSize"] == 65536
    assert row["fileId"] == 123


# ---------- امنیت مسیر و نام فایل ----------

@pytest.mark.parametrize("evil", [
    "../../etc/passwd", "..\\..\\windows\\system32\\x.exe", "/etc/passwd",
    "C:\\Windows\\System32\\x.exe", "%2e%2e%2fsecret", "a/../../b", ".", "..",
])
def test_sanitize_filename_blocks_traversal(evil):
    out = sanitize_filename(evil)
    assert "/" not in out and "\\" not in out
    assert ".." not in out
    assert out not in {"", ".", ".."}


def test_sanitize_filename_keeps_normal_names():
    assert sanitize_filename("report (1).pdf") == "report_1_.pdf"
    assert sanitize_filename("my-file_v2.TXT") == "my-file_v2.TXT"
    assert sanitize_filename("", fallback="fallback.bin") == "fallback.bin"


def test_filename_from_url_ignores_query_and_traversal():
    assert filename_from_url("https://x.test/files/photo.jpg?token=abc#frag") == "photo.jpg"
    assert filename_from_url("https://x.test/files/%2e%2e%2fsecret") == "secret"
    assert filename_from_url("https://x.test/", fallback="f.bin") == "f.bin"


def test_resolve_destination_blocks_escape(tmp_path):
    base = tmp_path / "allowed"
    base.mkdir()
    with pytest.raises(DownloadError):
        resolve_destination("../escape.txt", base_dir=base, filename="x.txt")
    with pytest.raises(DownloadError):
        resolve_destination(str(tmp_path / "outside.txt"), base_dir=base, filename="x.txt")


def test_resolve_destination_safe_inside(tmp_path):
    base = tmp_path / "allowed"
    base.mkdir()
    target = resolve_destination(base, base_dir=base, filename="../../evil.txt")
    assert target.parent == base.resolve()
    assert target.name == "evil.txt"


# ---------- نوشتن جریانی و اتمیک ----------

async def _agen(chunks):
    for c in chunks:
        yield c


async def test_write_stream_success(tmp_path):
    target = tmp_path / "out.bin"
    n = await write_stream_atomic(_agen([b"abc", b"def"]), target)
    assert n == 6
    assert target.read_bytes() == b"abcdef"
    assert not list(tmp_path.glob("*.part"))


async def test_write_stream_empty_file(tmp_path):
    target = tmp_path / "empty.bin"
    n = await write_stream_atomic(_agen([]), target)
    assert n == 0 and target.read_bytes() == b""


async def test_write_stream_large_file_bounded_memory(tmp_path):
    target = tmp_path / "big.bin"
    chunk = b"x" * 65536
    n = await write_stream_atomic(_agen([chunk] * 32), target, chunk_size=65536)
    assert n == 65536 * 32
    assert target.stat().st_size == n


async def test_write_stream_max_size_keeps_original(tmp_path):
    target = tmp_path / "f.bin"
    target.write_bytes(b"ORIGINAL")
    with pytest.raises(DownloadError):
        await write_stream_atomic(_agen([b"x" * 20]), target, max_size=10)
    assert target.read_bytes() == b"ORIGINAL"
    assert not list(tmp_path.glob("*.part"))


async def test_write_stream_network_error_keeps_original(tmp_path):
    target = tmp_path / "f.bin"
    target.write_bytes(b"ORIGINAL")

    async def failing():
        yield b"partial"
        raise ConnectionError("disconnect")

    with pytest.raises(DownloadError):
        await write_stream_atomic(failing(), target)
    assert target.read_bytes() == b"ORIGINAL"
    assert not list(tmp_path.glob("*.part"))


async def test_write_stream_timeout(tmp_path):
    target = tmp_path / "f.bin"

    async def timing_out():
        yield b"part"
        raise TimeoutError()

    with pytest.raises(DownloadError):
        await write_stream_atomic(timing_out(), target)
    assert not target.exists()


async def test_write_stream_duplicate_no_overwrite(tmp_path):
    target = tmp_path / "f.bin"
    target.write_bytes(b"one")
    await write_stream_atomic(_agen([b"two"]), target)
    assert target.read_bytes() == b"one"
    assert (tmp_path / "f (1).bin").read_bytes() == b"two"


async def test_write_stream_overwrite(tmp_path):
    target = tmp_path / "f.bin"
    target.write_bytes(b"one")
    await write_stream_atomic(_agen([b"two"]), target, overwrite=True)
    assert target.read_bytes() == b"two"


async def test_write_stream_concurrent(tmp_path):
    targets = [tmp_path / f"c{i}.bin" for i in range(8)]
    await __import__("asyncio").gather(*[
        write_stream_atomic(_agen([bytes([i]) * 100]), t) for i, t in enumerate(targets)
    ])
    for i, t in enumerate(targets):
        assert t.read_bytes() == bytes([i]) * 100


async def test_write_stream_progress_callback(tmp_path):
    seen = []
    await write_stream_atomic(
        _agen([b"aa", b"bbb"]), tmp_path / "p.bin",
        on_progress=lambda done, total: seen.append((done, total)),
    )
    assert seen == [(5, 5)]


async def test_write_stream_invalid_params(tmp_path):
    with pytest.raises(DownloadError):
        await write_stream_atomic(_agen([]), tmp_path / "a", max_size=0)
    with pytest.raises(DownloadError):
        await write_stream_atomic(_agen([]), tmp_path / "b", chunk_size=0)


# ---------- SelfBot API (Mock transport) ----------

class FakeTransport:
    def __init__(self, frame: bytes):
        self.frame = frame
        self.calls = []

    async def request(self, payload, timeout=None):
        self.calls.append((payload, timeout))
        return self.frame


def _make_bot(monkeypatch, file_bytes: bytes, url: str):
    """SelfBot با transport جعلی + سرور HTTP جعلی (httpx MockTransport)."""
    import httpx
    from badking.hybrid.proto import encode_named
    from badking.hybrid.rpc import registry
    from badking.hybrid.client import SelfBot

    spec = registry.get("files.GetNasimFileUrl")
    inner = encode_named(
        {"fileId": 7, "url": url, "timeout": 60000, "chunkSize": 4},
        {"fileId": 1, "url": 2, "timeout": 3, "chunkSize": 7},
    )
    frame = encode_named({"file_urls": inner}, spec.schema_for_naming())
    bot = SelfBot.__new__(SelfBot)
    bot._transport = FakeTransport(frame)
    bot.timeout = 30.0
    bot.permissions = None
    bot.registry = registry
    bot._my_id = 1

    class FakeStream:
        def __init__(self, data):
            self.data = data

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def raise_for_status(self):
            pass

        async def aiter_bytes(self, chunk_size=65536):
            for i in range(0, len(self.data), chunk_size):
                yield self.data[i:i + chunk_size]

    class FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def stream(self, method, url, **kw):
            return FakeStream(file_bytes)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return bot


async def test_get_file_url_parses_response(monkeypatch, tmp_path):
    bot = _make_bot(monkeypatch, b"data", "https://x.test/f.bin")
    info = await bot.get_file_url(7, 99)
    assert info["url"] == "https://x.test/f.bin"
    assert info["chunk_size"] == 4
    assert info["file_id"] == 7


async def test_download_file_end_to_end_mock(monkeypatch, tmp_path):
    bot = _make_bot(monkeypatch, b"HELLO-FILE", "https://x.test/photo.jpg")
    out = await bot.download_file(7, 99, destination=tmp_path)
    assert out.read_bytes() == b"HELLO-FILE"
    assert out.name == "photo.jpg"


async def test_download_file_traversal_in_url_name(monkeypatch, tmp_path):
    bot = _make_bot(monkeypatch, b"x", "https://x.test/files/%2e%2e%2fevil.exe")
    out = await bot.download_file(7, destination=tmp_path)
    assert out.parent == tmp_path
    assert ".." not in out.name


async def test_download_file_max_size(monkeypatch, tmp_path):
    bot = _make_bot(monkeypatch, b"TOO-BIG", "https://x.test/f.bin")
    with pytest.raises(DownloadError):
        await bot.download_file(7, destination=tmp_path, max_size=3)


async def test_message_media_info_and_download(monkeypatch, tmp_path):
    from badking.hybrid.client import Message, Peer

    raw = {"content": {"document": {"fileId": 7, "accessHash": 99, "name": "doc.pdf"}}}
    bot = _make_bot(monkeypatch, b"PDFDATA", "https://x.test/ignored")
    msg = Message(id=1, raw=raw, peer=Peer(id=1), _client=bot)
    assert msg.media_info()["file_id"] == 7
    out = await msg.download(destination=tmp_path)
    assert out.read_bytes() == b"PDFDATA"
    assert out.name == "doc.pdf"


async def test_message_without_media_raises(tmp_path):
    from badking.hybrid.client import Message, Peer
    msg = Message(id=1, raw={"content": {"text": {"value": "hi"}}}, peer=Peer(id=1))
    assert msg.media_info() is None
    with pytest.raises(DownloadError):
        await msg.download(destination=tmp_path)
