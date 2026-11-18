"""تستهای فاز ۵: Flow Builder، CLI، Adapter."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from badking.adapters import AdapterRegistry, BaleAdapter  # noqa: E402
from badking.cli.main import main  # noqa: E402
from badking.flows import Flow  # noqa: E402

FLOW = {
    "start": "welcome",
    "steps": {
        "welcome": {"type": "message", "text": "سلام!", "next": "ask"},
        "ask": {"type": "ask", "text": "نامت چیه؟", "save": "name", "next": "done"},
        "done": {"type": "message", "text": "خوش آمدی {name}!"},
    },
}


def test_flow_start():
    flow = Flow(FLOW)
    r = flow.start_session()
    assert r.messages == ["سلام!", "نامت چیه؟"]
    assert r.waiting_for == "ask"


def test_flow_full_conversation():
    flow = Flow(FLOW)
    s = flow.start_session()
    s = flow.handle(s.waiting_for, "علی", s.data)
    assert "خوش آمدی علی!" in s.messages
    assert s.ended


def test_flow_codegen():
    code = Flow(FLOW).to_python()
    assert "from badking import" in code
    assert "سلام!" in code


def test_cli_new(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main(["new", "mybot", "--greeting", "درود"])
    assert rc == 0
    assert (tmp_path / "mybot" / "bot.py").exists()
    assert "درود" in (tmp_path / "mybot" / "bot.py").read_text(encoding="utf-8")
    assert (tmp_path / "mybot" / "flow.json").exists()


def test_cli_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "flow.json").write_text(
        __import__("json").dumps(FLOW, ensure_ascii=False), encoding="utf-8"
    )
    inputs = iter(["علی"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    rc = main(["dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "سلام!" in out
    assert "خوش آمدی علی!" in out


def test_adapter_registry():
    class DummyAdapter:
        name = "dummy"

    reg = AdapterRegistry()
    reg.register("dummy", DummyAdapter())
    assert reg.names() == ["dummy"]
    assert isinstance(reg.get("dummy"), DummyAdapter)


def test_bale_adapter_type():
    from badking import Bot
    import httpx

    bot = Bot("1:X", client=httpx.AsyncClient())
    adapter = BaleAdapter(bot)
    assert adapter.name == "bale"
