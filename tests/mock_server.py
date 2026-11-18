"""سرور mock بله — تست WITHOUT توکن واقعی.

یک httpx MockTransport را شبیه API بله میکند.
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class BaleMock:
    """پاسخهای قابل پیشبینی برای متدهای بله."""

    def __init__(self):
        self.updates: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []
        self._msg_id = 100

    def add_message(self, text: str, chat_id: int = 123, user_id: int = 123,
                    first_name: str = "تستر") -> None:
        self.updates.append({
            "update_id": len(self.updates) + 1,
            "message": {
                "message_id": self._msg_id + len(self.updates),
                "date": 1700000000,
                "chat": {"id": chat_id, "type": "private", "first_name": first_name},
                "from": {"id": user_id, "is_bot": False, "first_name": first_name},
                "text": text,
            },
        })

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = path.rsplit("/", 1)[-1]

        if request.method == "GET" and not path.endswith("/getMe"):
            body = request.url.params.get("text")  # GET query
        try:
            payload = json.loads(request.content) if request.content else {}
        except Exception:
            payload = {}

        def ok(result: Any) -> httpx.Response:
            return httpx.Response(200, json={"ok": True, "result": result})

        if method == "getMe":
            return ok({"id": 999, "is_bot": True, "first_name": "BadKing Test Bot",
                       "username": "badking_test_bot"})
        if method == "getUpdates":
            offset = int(payload.get("offset") or 0)
            result = [u for u in self.updates if u["update_id"] >= offset]
            return ok(result)
        if method == "sendMessage":
            self.sent.append(payload)
            chat_id = payload.get("chat_id", 123)
            return ok({
                "message_id": self._msg_id + len(self.sent),
                "date": 1700000001,
                "chat": {"id": chat_id, "type": "private", "first_name": "تستر"},
                "text": payload.get("text"),
            })
        if method == "answerCallbackQuery":
            return ok(True)
        if method == "deleteMessage":
            return ok(True)
        # خطای نمونه برای تست raise_for_response
        if method == "forceError":
            return httpx.Response(200, json={"ok": False, "error_code": 401,
                                             "description": "Unauthorized"})
        return ok(True)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)
