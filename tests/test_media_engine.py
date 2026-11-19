"""تست Media Engine — امنیت فایل و رفتار درست."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from badking.media import MediaEngine, MediaError, MediaInfo
from badking.media.engine import (
    check_mime_matches,
    safe_filename,
    validate_extension,
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------- امنیت نام فایل ----------

class TestSafeFilename:
    def test_path_traversal_unix(self):
        assert safe_filename("../../etc/passwd") == "passwd"

    def test_path_traversal_windows(self):
        assert safe_filename("..\\..\\windows\\system32\\config") == "config"

    def test_absolute_path(self):
        assert safe_filename("/etc/shadow") == "shadow"

    def test_nested_path(self):
        assert safe_filename("a/b/c/report.pdf") == "report.pdf"

    def test_empty(self):
        assert safe_filename("") == "file"

    def test_only_dots(self):
        assert safe_filename("...") == "file"

    def test_dot_dot(self):
        assert safe_filename("..") == "file"

    def test_control_chars_removed(self):
        assert "\x00" not in safe_filename("a\x00b.txt")

    def test_windows_reserved_chars(self):
        result = safe_filename('a<b>c:d"e|f?g*h.txt')
        for char in '<>:"|?*':
            assert char not in result

    def test_leading_trailing_dots_stripped(self):
        assert safe_filename(".hidden.") == "hidden"

    def test_long_name_truncated(self):
        result = safe_filename("x" * 500 + ".pdf")
        assert len(result) <= 200
        assert result.endswith(".pdf")

    def test_persian_name_preserved(self):
        assert safe_filename("گزارش سالانه.pdf") == "گزارش سالانه.pdf"

    def test_custom_fallback(self):
        assert safe_filename("", fallback="x.bin") == "x.bin"


# ---------- پسوند ----------

class TestValidateExtension:
    def test_allowed(self):
        assert validate_extension("a.pdf") == ".pdf"
        assert validate_extension("a.JPG") == ".jpg"

    def test_rejected(self):
        with pytest.raises(MediaError) as info:
            validate_extension("malware.exe")
        assert "مجاز نیست" in str(info.value)

    def test_no_extension(self):
        with pytest.raises(MediaError) as info:
            validate_extension("README")
        assert "پسوند ندارد" in str(info.value)

    def test_custom_allow_list(self):
        assert validate_extension("a.exe", allow={".exe"}) == ".exe"

    def test_script_rejected(self):
        for bad in ("x.sh", "x.bat", "x.ps1", "x.py", "x.dll"):
            with pytest.raises(MediaError):
                validate_extension(bad)


# ---------- MIME ----------

class TestMimeMatch:
    def test_matching(self):
        assert check_mime_matches("photo.jpg", "image/jpeg") is True

    def test_family_match(self):
        assert check_mime_matches("photo.jpg", "image/png") is True

    def test_mismatch(self):
        assert check_mime_matches("photo.jpg", "application/x-msdownload") is False

    def test_empty_mime_ok(self):
        assert check_mime_matches("photo.jpg", "") is True

    def test_unknown_extension_ok(self):
        assert check_mime_matches("x.unknownext", "anything/here") is True


# ---------- MediaInfo ----------

class TestMediaInfo:
    def test_extension_from_name(self):
        assert MediaInfo(file_id="1", file_name="a.PDF").extension == ".pdf"

    def test_extension_from_mime(self):
        info = MediaInfo(file_id="1", mime_type="image/jpeg")
        assert info.extension in {".jpg", ".jpeg"}

    def test_no_extension(self):
        assert MediaInfo(file_id="1").extension == ""

    def test_is_image(self):
        assert MediaInfo(file_id="1", mime_type="image/png").is_image is True
        assert MediaInfo(file_id="1", file_name="a.jpg").is_image is True
        assert MediaInfo(file_id="1", file_name="a.pdf").is_image is False

    def test_is_video(self):
        assert MediaInfo(file_id="1", file_name="a.mp4").is_video is True
        assert MediaInfo(file_id="1", mime_type="video/mp4").is_video is True

    def test_is_audio(self):
        assert MediaInfo(file_id="1", file_name="a.mp3").is_audio is True
        assert MediaInfo(file_id="1", mime_type="audio/ogg").is_audio is True

    def test_human_size(self):
        assert "بایت" in MediaInfo(file_id="1", size=500).human_size()
        assert "کیلوبایت" in MediaInfo(file_id="1", size=2048).human_size()
        assert "مگابایت" in MediaInfo(file_id="1", size=5 * 1024 * 1024).human_size()
        assert "گیگابایت" in MediaInfo(file_id="1", size=3 * 1024**3).human_size()


# ---------- Engine ----------

class FakeBot:
    """کلاینت تقلبی برای تست دانلود."""

    def __init__(self, content: bytes = b"data", fail: bool = False) -> None:
        self.content = content
        self.fail = fail
        self.downloads: list[str] = []

    async def download_file(self, file_id, destination, on_progress=None):
        if self.fail:
            raise RuntimeError("شبکه قطع شد")
        self.downloads.append(file_id)
        Path(destination).write_bytes(self.content)
        if on_progress:
            result = on_progress(len(self.content), len(self.content))
            if asyncio.iscoroutine(result):
                await result

    async def get_file(self, file_id):
        class Raw:
            file_name = "a.jpg"
            mime_type = "image/jpeg"
            file_size = 1234
            duration = 0
            width = 100
            height = 100
            thumbnail = ""

        return Raw()

    async def send_document(self, chat_id, path, caption=""):
        return {"chat_id": chat_id, "path": path, "caption": caption}

    async def send_photo(self, chat_id, path, caption=""):
        return {"chat_id": chat_id, "path": path, "caption": caption}


class TestMediaEngine:
    def make(self, tmp_path, **kwargs):
        return MediaEngine(FakeBot(**kwargs), cache_dir=tmp_path)

    def test_download_creates_file(self, tmp_path):
        engine = self.make(tmp_path)
        path = run(engine.download("f1", file_name="a.jpg"))
        assert path.exists()
        assert path.read_bytes() == b"data"

    def test_download_uses_cache(self, tmp_path):
        bot = FakeBot()
        engine = MediaEngine(bot, cache_dir=tmp_path)
        run(engine.download("f1", file_name="a.jpg"))
        run(engine.download("f1", file_name="a.jpg"))
        assert len(bot.downloads) == 1

    def test_force_bypasses_cache(self, tmp_path):
        bot = FakeBot()
        engine = MediaEngine(bot, cache_dir=tmp_path)
        run(engine.download("f1", file_name="a.jpg"))
        run(engine.download("f1", file_name="a.jpg", force=True))
        assert len(bot.downloads) == 2

    def test_progress_called(self, tmp_path):
        engine = self.make(tmp_path)
        seen = []

        async def on_progress(done, total):
            seen.append((done, total))

        run(engine.download("f1", file_name="a.jpg", on_progress=on_progress))
        assert seen == [(4, 4)]

    def test_download_failure_raises(self, tmp_path):
        engine = self.make(tmp_path, fail=True)
        with pytest.raises(MediaError) as info:
            run(engine.download("f1", file_name="a.jpg"))
        assert "دانلود نشد" in str(info.value)

    def test_no_bot_raises(self, tmp_path):
        engine = MediaEngine(None, cache_dir=tmp_path)
        with pytest.raises(MediaError) as info:
            run(engine.download("f1"))
        assert "کلاینت" in str(info.value)

    def test_size_limit(self, tmp_path):
        bot = FakeBot(content=b"x" * 100)
        engine = MediaEngine(bot, cache_dir=tmp_path, max_size=50)
        with pytest.raises(MediaError) as info:
            run(engine.download("f1", file_name="a.jpg"))
        assert "بیشتر" in str(info.value)
        # فایل بزرگ نباید بماند
        assert list(tmp_path.glob("*_a.jpg")) == []

    def test_unsafe_name_sanitized(self, tmp_path):
        engine = self.make(tmp_path)
        path = run(engine.download("f1", file_name="../../evil.jpg"))
        assert ".." not in path.name
        assert path.parent == tmp_path

    def test_download_many(self, tmp_path):
        engine = self.make(tmp_path)
        paths = run(engine.download_many(["a", "b", "c"]))
        assert len(paths) == 3
        assert all(p is not None and p.exists() for p in paths)

    def test_download_many_isolates_failure(self, tmp_path):
        engine = self.make(tmp_path, fail=True)
        paths = run(engine.download_many(["a", "b"]))
        assert paths == [None, None]

    def test_upload_missing_file(self, tmp_path):
        engine = self.make(tmp_path)
        with pytest.raises(MediaError) as info:
            run(engine.upload(1, tmp_path / "nope.pdf"))
        assert "فایل نیست" in str(info.value)

    def test_upload_rejects_bad_extension(self, tmp_path):
        engine = self.make(tmp_path)
        bad = tmp_path / "evil.exe"
        bad.write_bytes(b"x")
        with pytest.raises(MediaError):
            run(engine.upload(1, bad))

    def test_upload_auto_detects_photo(self, tmp_path):
        engine = self.make(tmp_path)
        photo = tmp_path / "a.jpg"
        photo.write_bytes(b"x")
        result = run(engine.upload(1, photo))
        assert result["path"].endswith("a.jpg")

    def test_upload_auto_detects_document(self, tmp_path):
        engine = self.make(tmp_path)
        doc = tmp_path / "a.pdf"
        doc.write_bytes(b"x")
        result = run(engine.upload(1, doc))
        assert result["chat_id"] == 1

    def test_upload_oversize(self, tmp_path):
        engine = MediaEngine(FakeBot(), cache_dir=tmp_path, max_size=10)
        big = tmp_path / "a.pdf"
        big.write_bytes(b"x" * 100)
        with pytest.raises(MediaError) as info:
            run(engine.upload(1, big))
        assert "بیشتر" in str(info.value)

    def test_info(self, tmp_path):
        engine = self.make(tmp_path)
        info = run(engine.info("f1"))
        assert info.file_name == "a.jpg"
        assert info.is_image is True

    def test_validate_rejects_oversize(self, tmp_path):
        engine = MediaEngine(FakeBot(), cache_dir=tmp_path, max_size=100)
        with pytest.raises(MediaError):
            engine.validate(MediaInfo(file_id="1", size=1000))

    def test_validate_rejects_mime_mismatch(self, tmp_path):
        engine = self.make(tmp_path)
        with pytest.raises(MediaError) as info:
            engine.validate(
                MediaInfo(
                    file_id="1",
                    file_name="photo.jpg",
                    mime_type="application/x-msdownload",
                )
            )
        assert "جعلی" in str(info.value)

    def test_cache_size_and_clear(self, tmp_path):
        engine = self.make(tmp_path)
        run(engine.download("f1", file_name="a.jpg"))
        assert engine.cache_size() == 4
        assert engine.clear_cache() == 1
        assert engine.cache_size() == 0

    def test_enforce_disk_limit(self, tmp_path):
        engine = self.make(tmp_path)
        for i in range(5):
            run(engine.download(f"f{i}", file_name=f"a{i}.jpg"))
        removed = engine.enforce_disk_limit(8)
        assert removed >= 3
        assert engine.cache_size() <= 8

    def test_disk_usage(self, tmp_path):
        engine = self.make(tmp_path)
        usage = engine.disk_usage()
        assert "cache_bytes" in usage
        assert usage["disk_free"] > 0

    def test_cached_path_none_when_missing(self, tmp_path):
        engine = self.make(tmp_path)
        assert engine.cached_path("nope") is None
