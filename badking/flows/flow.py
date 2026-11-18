"""Flow Builder — ساخت ربات بدون کد.

جریان ربات به صورت JSON/دیکشنری تعریف میشود:
{
  "start": "welcome",
  "steps": {
    "welcome": {"type": "message", "text": "سلام!", "next": "ask_name"},
    "ask_name": {"type": "ask", "text": "نامت چیه؟", "save": "name", "next": "done"},
    "done": {"type": "message", "text": "خوش آمدی {name}"}
  }
}
همچنین قابل تبدیل به کد پایتون (برای وقتی که ربات بزرگ شد).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FlowResult:
    messages: list[str] = field(default_factory=list)
    waiting_for: str | None = None
    ended: bool = False
    data: dict[str, Any] = field(default_factory=dict)


class Flow:
    """اجرای جریان مکالمه به ازای هر کاربر."""

    def __init__(self, definition: dict[str, Any]):
        self.start = definition.get("start")
        self.steps = definition.get("steps", {})
        if not self.start or self.start not in self.steps:
            raise ValueError("جریان باید start معتبر داشته باشد")

    @classmethod
    def from_json(cls, path: str | Path) -> "Flow":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def _render(self, template: str, data: dict[str, Any]) -> str:
        try:
            return template.format(**data)
        except (KeyError, ValueError):
            return template

    def start_session(self) -> FlowResult:
        """شروع جریان: اجرای گام آغازین."""
        result = FlowResult()
        self._run_step(self.start, "", result)
        return result

    def handle(self, current_step: str, user_input: str, data: dict[str, Any]) -> FlowResult:
        """ادامه جریان با ورودی کاربر."""
        result = FlowResult(data=dict(data))
        step = self.steps.get(current_step, {})
        save_as = step.get("save")
        if save_as:
            result.data[save_as] = user_input
        next_step = step.get("next")
        if next_step:
            self._run_step(next_step, user_input, result)
        else:
            result.ended = True
        return result

    def _run_step(self, step_name: str, user_input: str, result: FlowResult) -> None:
        step = self.steps.get(step_name)
        if not step:
            result.ended = True
            return
        kind = step.get("type", "message")
        text = step.get("text", "")
        if kind == "message":
            result.messages.append(self._render(text, result.data))
            if step.get("next"):
                self._run_step(step["next"], user_input, result)
            else:
                result.ended = True
        elif kind == "ask":
            result.messages.append(self._render(text, result.data))
            result.waiting_for = step_name
            result.ended = False
        elif kind == "condition":
            # شرط ساده: برابری ورودی با گزینهها
            options = step.get("options", {})
            target = options.get(user_input.strip(), step.get("default"))
            if target:
                self._run_step(target, user_input, result)
            else:
                result.ended = True
        elif kind == "end":
            result.messages.append(self._render(text, result.data))
            result.ended = True

    def to_python(self, bot_var: str = "bot") -> str:
        """تبدیل جریان به کد پایتون قابل اجرا."""
        lines = [
            "# کد تولیدشده توسط BADKING Flow Builder",
            "from badking import Bot, Dispatcher, F",
            "",
            f"bot = Bot('TOKEN')",
            "dp = Dispatcher()",
            "",
        ]
        for name, step in self.steps.items():
            if step.get("type") == "message":
                lines.append(f"# گام: {name}")
                lines.append(f"async def step_{name}(message, bot):")
                lines.append(f"    await bot.send_message(message.chat.id, {step.get('text', '')!r})")
                lines.append("")
        lines.append("asyncio.run(bot.polling(dp))")
        return "\n".join(lines)
