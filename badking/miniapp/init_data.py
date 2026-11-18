"""اعتبارسنجی امن initData مینیاپ بله.

منبع: docs.bale.ai/miniapp
الگوریتم (مطابق مستندات):
  secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
  calculated  = HMAC_SHA256(key=secret_key, msg=query_string)
  مقایسه با hash ارسالشده (با compare_digest)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode


class InvalidInitData(Exception):
    """امضای initData نامعتبر یا منقضی است."""


@dataclass
class WebAppUser:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WebAppUser":
        return cls(
            id=int(d.get("id", 0)),
            first_name=d.get("first_name", ""),
            last_name=d.get("last_name"),
            username=d.get("username"),
            photo_url=d.get("photo_url"),
        )


@dataclass
class WebAppInitData:
    query_id: str | None
    user: WebAppUser | None
    auth_date: int
    raw: dict[str, Any]

    def is_fresh(self, max_age: int = 86400) -> bool:
        """آیا initData تازه است؟ تاریخ آینده (تا ۳۰ ثانیه تحمل انحراف ساعت) مجاز است."""
        age = time.time() - self.auth_date
        return -30 <= age <= max_age


def _hmac_sha256(key: bytes, msg: str) -> str:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def validate_init_data(init_data: str, bot_token: str, *, max_age: int = 86400) -> WebAppInitData:
    """امضای initData را تأیید و دادهها را برمیگرداند. در صورت عدم اعتبار exception."""
    if not init_data:
        raise InvalidInitData("initData خالی است")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise InvalidInitData("hash وجود ندارد")

    # طبق مستندات رسمی بله: تمام فیلدها (بهجز hash) الفبایی مرتب شوند
    # و با \n به شکل key=value بههم متصل شوند (نه urlencode با &).
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated = _hmac_sha256(secret_key, data_check_string)

    if not hmac.compare_digest(calculated, received_hash):
        raise InvalidInitData("امضا نامعتبر است")

    # auth_date همیشه حضور دارد؛ نبودنش یعنی initData نامعتبر است
    auth_raw = data.get("auth_date")
    if not auth_raw:
        raise InvalidInitData("auth_date وجود ندارد")
    try:
        auth_date = int(auth_raw)
    except (TypeError, ValueError):
        raise InvalidInitData("auth_date نامعتبر است")
    age = time.time() - auth_date
    if age > max_age or age < -30:
        raise InvalidInitData("initData منقضی است یا تاریخ آینده دارد")

    user_data = None
    if "user" in data:
        try:
            user_data = WebAppUser.from_dict(json.loads(data["user"]))
        except Exception:
            user_data = None

    return WebAppInitData(
        query_id=data.get("query_id"),
        user=user_data,
        auth_date=auth_date,
        raw=data,
    )


def generate_test_init_data(bot_token: str, user_id: int = 123, first_name: str = "تستر") -> str:
    """فقط برای تست و مثال — initData معتبر میسازد."""
    user = json.dumps({"id": user_id, "first_name": first_name}, ensure_ascii=False,
                      separators=(",", ":"))
    data = {"query_id": "AAHd", "user": user, "auth_date": str(int(time.time()))}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    data["hash"] = _hmac_sha256(secret_key, check_string)
    return urlencode(list(data.items()))
