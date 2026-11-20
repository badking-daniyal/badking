"""تست Security Scanner — یافتههای واقعی، بدون Fake."""

from __future__ import annotations

import pytest

from badking.security import Finding, ScanReport, SecurityScanner, severity_rank
from badking.cli.main import build_parser, cmd_security


def test_severity_order():
    assert severity_rank("CRITICAL") < severity_rank("HIGH")
    assert severity_rank("HIGH") < severity_rank("LOW")
    assert severity_rank("UNKNOWN") == 5


def test_clean_file(tmp_path):
    path = tmp_path / "clean.py"
    path.write_text("x = 1\nprint(x)\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert report.findings == []
    assert report.files_scanned == 1


def test_bot_token_detected(tmp_path):
    path = tmp_path / "bot.py"
    path.write_text('TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"\n', encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    codes = [f.code for f in report.findings]
    assert "BOT_TOKEN_HARDCODED" in codes
    assert report.findings[0].severity == "CRITICAL"


def test_secret_is_redacted(tmp_path):
    path = tmp_path / "bot.py"
    path.write_text('TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"\n', encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    finding = next(f for f in report.findings if f.code == "BOT_TOKEN_HARDCODED")
    assert "AAHdqTcv" not in finding.evidence
    assert "*" in finding.evidence


def test_eval_detected(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("result = eval(user_input)\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert any(f.code == "EVAL_USAGE" and f.severity == "CRITICAL" for f in report.findings)


def test_exec_detected(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("exec(code)\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert any(f.code == "EXEC_USAGE" for f in report.findings)


def test_shell_true_detected(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("subprocess.run(cmd, shell=True)\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert any(f.code == "SHELL_TRUE" and f.severity == "HIGH" for f in report.findings)


def test_ssl_disabled_detected(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("requests.get(url, verify=False)\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert any(f.code == "SSL_DISABLED" for f in report.findings)


def test_silent_exception_detected(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("try:\n    x = 1\nexcept Exception:\n    pass\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert any(f.code == "SILENT_EXCEPTION" for f in report.findings)


def test_bare_except_detected(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("try:\n    x = 1\nexcept:\n    print('x')\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert any(f.code == "BARE_EXCEPT" for f in report.findings)


def test_assert_detected(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("assert user.is_admin\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert any(f.code == "ASSERT_IN_CODE" for f in report.findings)


def test_private_key_detected(tmp_path):
    path = tmp_path / "key.pem"
    path.write_text("-----BEGIN PRIVATE KEY-----\nabc\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert any(f.code == "PRIVATE_KEY" and f.severity == "CRITICAL" for f in report.findings)


def test_comment_line_skipped_for_code_patterns(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("# eval(user_input)\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert not any(f.code == "EVAL_USAGE" for f in report.findings)


def test_scan_directory(tmp_path):
    (tmp_path / "a.py").write_text("eval(x)\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("x = 1\n", encoding="utf-8")
    sub = tmp_path / "__pycache__"
    sub.mkdir()
    (sub / "c.py").write_text("eval(x)\n", encoding="utf-8")

    report = SecurityScanner().scan(tmp_path)
    assert report.files_scanned == 2
    assert report.files_skipped >= 1
    assert len(report.findings) == 1


def test_report_counts_and_dict(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("eval(x)\nverify=False\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    counts = report.counts()
    assert counts["CRITICAL"] >= 1
    assert counts["HIGH"] >= 1
    data = report.to_dict()
    assert "findings" in data
    assert data["counts"]["CRITICAL"] >= 1


def test_report_summary(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("x = 1\n", encoding="utf-8")
    report = SecurityScanner().scan_file(path)
    assert "مشکلی پیدا نشد" in report.summary()


def test_finding_str():
    f = Finding(severity="HIGH", code="X", message="test", path="a.py", line=3)
    assert "a.py:3" in str(f)


def test_cli_parser_has_security_scan():
    parser = build_parser()
    args = parser.parse_args(["security", "scan", "."])
    assert args.func is cmd_security
    assert args.path == "."


def test_cli_scan_clean(tmp_path, capsys):
    (tmp_path / "x.py").write_text("x = 1\n", encoding="utf-8")
    args = build_parser().parse_args(["security", "scan", str(tmp_path)])
    code = cmd_security(args)
    out = capsys.readouterr().out
    assert code == 0
    assert "اسکن امنیتی" in out


def test_cli_scan_blocking(tmp_path, capsys):
    (tmp_path / "x.py").write_text("eval(x)\n", encoding="utf-8")
    args = build_parser().parse_args(["security", "scan", str(tmp_path)])
    code = cmd_security(args)
    assert code == 1


def test_cli_json_output(tmp_path, capsys):
    (tmp_path / "x.py").write_text("x = 1\n", encoding="utf-8")
    args = build_parser().parse_args(["security", "scan", str(tmp_path), "--json"])
    cmd_security(args)
    out = capsys.readouterr().out
    assert '"findings"' in out
