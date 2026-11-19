"""تست ابزارهای عیب‌یابی CLI — همه آفلاین، بدون شبکه."""

from __future__ import annotations

import sys

import pytest

from badking.cli.doctor import (
    check_disk,
    check_env_file,
    check_git,
    check_import,
    check_network,
    check_optional_deps,
    check_python,
    check_session_file,
    check_token,
    check_write_permission,
    run_check,
    run_doctor,
    run_info,
)


class TestChecks:
    def test_python_version(self):
        good, detail, hint = check_python()
        assert good is True
        assert detail.count(".") == 2
        assert hint == ""

    def test_import(self):
        good, detail, hint = check_import()
        assert good is True
        assert detail  # نسخه
        assert hint == ""

    def test_optional_deps_returns_all(self):
        results = check_optional_deps()
        names = {name for _, name, _ in results}
        assert "websockets" in names
        assert "aiohttp" in names
        # همه یا نصب‌اند یا نیستند، ولی همه گزارش می‌شوند
        assert len(results) == 4

    def test_network_bad_host(self):
        # دامنه‌ای که قطعاً حل نمی‌شود
        good, detail, hint = check_network("this-host-does-not-exist-badking.invalid")
        assert good is False
        assert hint

    def test_token_absent(self, monkeypatch):
        for var in ("BADKING_TOKEN", "BALE_TOKEN", "BOT_TOKEN", "TELEGRAM_BOT_TOKEN"):
            monkeypatch.delenv(var, raising=False)
        good, detail, hint = check_token()
        assert good is False
        assert hint

    def test_token_present(self, monkeypatch):
        monkeypatch.setenv("BADKING_TOKEN", "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw")
        good, detail, hint = check_token()
        assert good is True
        # توکن کامل نباید نمایش داده شود
        assert "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" not in detail
        assert "…" in detail

    def test_env_file_absent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        good, _, hint = check_env_file()
        assert good is False
        assert hint

    def test_env_file_present(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("X=1", encoding="utf-8")
        good, detail, _ = check_env_file()
        assert good is True
        assert ".env" in detail

    def test_session_file_absent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        good, _, hint = check_session_file()
        assert good is False
        assert "login" in hint

    def test_session_file_present(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "bot.session").write_bytes(b"x" * 100)
        good, detail, _ = check_session_file()
        assert good is True
        assert "bot.session" in detail

    def test_write_permission(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        good, detail, _ = check_write_permission()
        assert good is True
        # فایل آزمایشی نباید بماند
        assert not (tmp_path / ".badking_write_test").exists()

    def test_disk(self):
        good, detail, _ = check_disk()
        assert good is True
        assert "GB" in detail

    def test_git_returns_tuple(self):
        good, detail, hint = check_git()
        assert isinstance(good, bool)
        assert isinstance(detail, str)


class TestRunDoctor:
    def test_returns_zero_when_healthy(self, capsys):
        rc = run_doctor(network=False)
        out = capsys.readouterr().out
        assert "BADKING doctor" in out
        assert "پایتون" in out
        assert rc == 0

    def test_shows_sections(self, capsys):
        run_doctor(network=False)
        out = capsys.readouterr().out
        for section in ("محیط", "بسته", "پیکربندی", "دسترسی"):
            assert section in out

    def test_network_skipped_when_disabled(self, capsys):
        run_doctor(network=False)
        out = capsys.readouterr().out
        assert "سرور بله" not in out

    def test_verbose_mode(self, capsys):
        rc = run_doctor(network=False, verbose=True)
        assert rc in (0, 1)


class TestRunInfo:
    def test_prints_version(self, capsys):
        rc = run_info()
        out = capsys.readouterr().out
        assert rc == 0
        assert "BADKING" in out
        assert "پایتون" in out

    def test_shows_rpc_count(self, capsys):
        run_info()
        out = capsys.readouterr().out
        assert "RPC" in out
        assert "79" in out

    def test_shows_features(self, capsys):
        run_info()
        out = capsys.readouterr().out
        assert "Self-bot" in out
        assert "FSM" in out
        assert "تاب‌آوری" in out


class TestRunCheck:
    def test_clean_file(self, tmp_path, capsys):
        (tmp_path / "good.py").write_text("x = 1\n", encoding="utf-8")
        rc = run_check(str(tmp_path))
        out = capsys.readouterr().out
        assert rc == 0
        assert "بدون خطای نحوی" in out

    def test_syntax_error_detected(self, tmp_path, capsys):
        (tmp_path / "bad.py").write_text("def broken(:\n", encoding="utf-8")
        rc = run_check(str(tmp_path))
        out = capsys.readouterr().out
        assert rc == 1
        assert "bad.py" in out

    def test_missing_path(self, tmp_path, capsys):
        rc = run_check(str(tmp_path / "nope"))
        assert rc == 1

    def test_empty_dir(self, tmp_path, capsys):
        rc = run_check(str(tmp_path))
        out = capsys.readouterr().out
        assert rc == 0
        assert "پیدا نشد" in out

    def test_skips_pycache(self, tmp_path, capsys):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "junk.py").write_text("def broken(:\n", encoding="utf-8")
        (tmp_path / "good.py").write_text("x = 1\n", encoding="utf-8")
        rc = run_check(str(tmp_path))
        assert rc == 0

    def test_counts_multiple_files(self, tmp_path, capsys):
        for i in range(3):
            (tmp_path / f"f{i}.py").write_text("x = 1\n", encoding="utf-8")
        run_check(str(tmp_path))
        out = capsys.readouterr().out
        assert "3 فایل" in out
