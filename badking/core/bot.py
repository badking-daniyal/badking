"""Bot — کلاینت Bot API رسمی بله.

تمام درخواستها به https://tapi.bale.ai/bot<token>/METHOD_NAME میروند.
پاسخ ok=false تبدیل به exception میشود.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from ..types.keyboard import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from ..types.media import File
from ..types.message import Message, MessageId
from ..types.update import Update
from ..types.user import User
from .constants import API_BASE, DEFAULT_TIMEOUT, Limits
from .errors import NetworkError, RateLimitError, raise_for_response


def _clean(obj: Any) -> Any:
    """حذف مقادیر None و تبدیل مدلها به dict."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(by_alias=True, exclude_none=True, mode="json")
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    return obj


class Bot:
    """کلاینت اصلی بازو.

    مثال:
        bot = Bot("123456:ABC...")
        me = await bot.get_me()
    """

    def __init__(
        self,
        token: str,
        *,
        base_url: str = API_BASE,
        business: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
        limits: Limits | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        if not token or ":" not in token:
            raise ValueError("توکن نامعتبر است. فرمت: 123456789:abcdef...")
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.business = business
        self.timeout = timeout
        self.limits = limits or Limits()
        self._client = client
        self._offset = 0
        self._me: User | None = None

    @property
    def api_url(self) -> str:
        path = "/business" if self.business else ""
        return f"{self.base_url}{path}/bot{self.token}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def request(self, method: str, params: dict[str, Any] | None = None,
                      files: dict[str, Any] | None = None) -> Any:
        """فراخوانی خام متد API. در صورت خطا exception پرتاب میکند."""
        url = f"{self.api_url}/{method}"
        payload = _clean(params or {})
        client = await self._get_client()
        try:
            if files:
                resp = await client.post(url, data=payload, files=files)
            else:
                resp = await client.post(url, json=payload)
        except httpx.HTTPError as e:
            raise NetworkError(f"خطای شبکه در {method}: {e}", method=method) from e

        try:
            data = resp.json()
        except Exception as e:
            raise NetworkError(f"پاسخ نامعتبر از {method}: {resp.text[:200]}", method=method) from e

        if data.get("ok") is not True:
            # هم ok=False و هم پاسخ بدون کلید ok (ساختار نامعتبر) خطا محسوب شوند
            code = data.get("error_code")
            params_err = data.get("parameters") or {}
            self.limits.calibrate_from_response(params_err.get("retry_after"), code)
            raise_for_response(data, method=method)
        return data.get("result")

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "Bot":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ---------- متدهای اصلی ----------

    async def get_me(self) -> User:
        r = await self.request("getMe")
        self._me = User.model_validate(r)
        return self._me

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | dict | None = None,
        disable_web_page_preview: bool | None = None,
        message_thread_id: int | None = None,
        **kwargs: Any,
    ) -> Message:
        params = {
            "chat_id": chat_id, "text": text,
            "reply_to_message_id": reply_to_message_id,
            "reply_markup": reply_markup,
            "disable_web_page_preview": disable_web_page_preview,
            "message_thread_id": message_thread_id,
            **kwargs,
        }
        return Message.model_validate(await self.request("sendMessage", params))

    async def forward_message(self, chat_id: int | str, from_chat_id: int | str,
                              message_id: int, **kwargs: Any) -> Message:
        return Message.model_validate(await self.request("forwardMessage", {
            "chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id, **kwargs,
        }))

    async def copy_message(self, chat_id: int | str, from_chat_id: int | str,
                           message_id: int, **kwargs: Any) -> MessageId:
        return MessageId.model_validate(await self.request("copyMessage", {
            "chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id, **kwargs,
        }))

    async def send_photo(self, chat_id: int | str, photo: str, *, caption: str | None = None,
                         reply_markup: Any = None, **kwargs: Any) -> Message:
        return Message.model_validate(await self.request("sendPhoto", {
            "chat_id": chat_id, "photo": photo, "caption": caption,
            "reply_markup": reply_markup, **kwargs,
        }))

    async def send_document(self, chat_id: int | str, document: str, *, caption: str | None = None,
                            reply_markup: Any = None, **kwargs: Any) -> Message:
        return Message.model_validate(await self.request("sendDocument", {
            "chat_id": chat_id, "document": document, "caption": caption,
            "reply_markup": reply_markup, **kwargs,
        }))

    async def send_audio(self, chat_id: int | str, audio: str, **kwargs: Any) -> Message:
        return Message.model_validate(await self.request("sendAudio", {
            "chat_id": chat_id, "audio": audio, **kwargs,
        }))

    async def send_video(self, chat_id: int | str, video: str, **kwargs: Any) -> Message:
        return Message.model_validate(await self.request("sendVideo", {
            "chat_id": chat_id, "video": video, **kwargs,
        }))

    async def send_animation(self, chat_id: int | str, animation: str, **kwargs: Any) -> Message:
        return Message.model_validate(await self.request("sendAnimation", {
            "chat_id": chat_id, "animation": animation, **kwargs,
        }))

    async def send_voice(self, chat_id: int | str, voice: str, **kwargs: Any) -> Message:
        return Message.model_validate(await self.request("sendVoice", {
            "chat_id": chat_id, "voice": voice, **kwargs,
        }))

    async def send_location(self, chat_id: int | str, latitude: float, longitude: float,
                            **kwargs: Any) -> Message:
        return Message.model_validate(await self.request("sendLocation", {
            "chat_id": chat_id, "latitude": latitude, "longitude": longitude, **kwargs,
        }))

    async def send_contact(self, chat_id: int | str, phone_number: str, first_name: str,
                           **kwargs: Any) -> Message:
        return Message.model_validate(await self.request("sendContact", {
            "chat_id": chat_id, "phone_number": phone_number, "first_name": first_name, **kwargs,
        }))

    async def send_chat_action(self, chat_id: int | str, action: str) -> bool:
        return bool(await self.request("sendChatAction", {"chat_id": chat_id, "action": action}))

    async def get_file(self, file_id: str) -> File:
        return File.model_validate(await self.request("getFile", {"file_id": file_id}))

    async def download_file(self, file_id: str) -> bytes:
        f = await self.get_file(file_id)
        url = f.download_url(self.token, base_url=self.base_url)
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise NetworkError(f"خطای دانلود فایل: {e}", method="downloadFile") from e
        return resp.content

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None,
                                     **kwargs: Any) -> bool:
        return bool(await self.request("answerCallbackQuery", {
            "callback_query_id": callback_query_id, "text": text, **kwargs,
        }))

    async def edit_message_text(self, chat_id: int | str, message_id: int, text: str,
                                **kwargs: Any) -> Message:
        return Message.model_validate(await self.request("editMessageText", {
            "chat_id": chat_id, "message_id": message_id, "text": text, **kwargs,
        }))

    async def delete_message(self, chat_id: int | str, message_id: int) -> bool:
        return bool(await self.request("deleteMessage", {
            "chat_id": chat_id, "message_id": message_id,
        }))

    async def get_chat(self, chat_id: int | str) -> dict[str, Any]:
        return await self.request("getChat", {"chat_id": chat_id})

    async def get_chat_member(self, chat_id: int | str, user_id: int) -> dict[str, Any]:
        return await self.request("getChatMember", {"chat_id": chat_id, "user_id": user_id})

    async def get_chat_administrators(self, chat_id: int | str) -> list[dict[str, Any]]:
        return await self.request("getChatAdministrators", {"chat_id": chat_id})

    async def get_chat_members_count(self, chat_id: int | str) -> int:
        return int(await self.request("getChatMembersCount", {"chat_id": chat_id}))

    async def set_webhook(self, url: str, **kwargs: Any) -> bool:
        return bool(await self.request("setWebhook", {"url": url, **kwargs}))

    async def delete_webhook(self) -> bool:
        return bool(await self.request("deleteWebhook"))

    async def get_webhook_info(self) -> dict[str, Any]:
        return await self.request("getWebhookInfo")

    async def set_my_commands(self, commands: list[dict[str, str]]) -> bool:
        return bool(await self.request("setMyCommands", {"commands": commands}))

    async def get_updates(self, offset: int | None = None, limit: int | None = None,
                          timeout: int | None = None) -> list[Update]:
        params: dict[str, Any] = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if timeout is not None:
            params["timeout"] = timeout
        raw = await self.request("getUpdates", params)
        updates = [Update.model_validate(u) for u in (raw or [])]
        # نکته: offset را اینجا پیشروی نمیکنیم. مسئولیت polling است که بعد از
        # پردازش موفق هندلرها آنرا جلو ببرد، تا آپدیتی گم نشود (at-least-once).
        return updates

    # ---------- Long Polling ----------

    async def polling(self, dispatcher: Any, *, limit: int = 100, timeout: int = 10,
                      on_error: Any = None, offset_store: Any = None) -> None:
        """long polling حلقه اصلی. offset بهصورت خودکار ذخیره میشود."""
        if offset_store is not None:
            self._offset = offset_store.load()
        try:
            while True:
                try:
                    updates = await self.get_updates(offset=self._offset, limit=limit, timeout=timeout)
                    for update in updates:
                        # ابتدا پردازش، سپس پیشروی offset — اگر هندلر خطا دهد،
                        # همان آپدیت در تلاش بعدی دوباره خوانده میشود (گم نمیشود).
                        await dispatcher.process(update, self)
                        self._offset = update.update_id + 1
                        if offset_store is not None:
                            offset_store.save(self._offset)
                except RateLimitError as e:
                    # سقف 60 ثانیه: سرور نباید بتواند polling را طولانی متوقف کند
                    delay = min(float(e.retry_after or 1.0), 60.0)
                    await asyncio.sleep(delay)
                except NetworkError as e:
                    # قطع موقتی شبکه در long polling طبیعی است؛ پیام کوتاه، بدون traceback
                    if on_error:
                        await on_error(e) if asyncio.iscoroutinefunction(on_error) else on_error(e)
                    else:
                        import logging
                        logging.getLogger("badking").warning("اتصال موقتی قطع شد، تلاش مجدد...")
                    await asyncio.sleep(2)
                except Exception as e:
                    if on_error:
                        await on_error(e) if asyncio.iscoroutinefunction(on_error) else on_error(e)
                    else:
                        import logging
                        logging.getLogger("badking").exception("خطا در polling")
                    await asyncio.sleep(2)
        except asyncio.CancelledError:
            await self.close()
            raise
