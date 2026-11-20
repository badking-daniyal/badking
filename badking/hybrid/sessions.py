"""SessionManager — کنترل چند اکانت self-bot، جایگزین پوشه sessions/.

کاری که main-3.py با فایل‌های .bale پراکنده میکرد، اینجا امن و مرکزی
انجام می‌شود:

    from badking.hybrid import SessionManager

    mgr = SessionManager("sessions.bks", password="...")

    # ساخت سشن با شماره + کد SMS
    result = await mgr.create_session("09123456789", code_prompt=my_prompt)

    # لیست، حذف، بررسی سلامت
    mgr.list_accounts()
    await mgr.check_all()

    # بکاپ / ریستور (جایگزین backup.zip)
    mgr.export_zip("backup.zip")
    mgr.import_zip("backup.zip")

چرا بهتر از فایل پراکنده:
- یک فایل رمزنگاری‌شده به جای صدها فایل .bale
- نام فایل از شماره کاربر میآید، نه ورودی خام (Path Traversal ندارد)
- بکاپ/ریستور اتمیک و تأییدشده با هش
- هر اکانت یک Session جدا، قابل بارگذاری روی SelfBot

هشدار: self-bot غیررسمی است و می‌تواند اکانت را مسدود کند.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .auth import AuthError, AuthFlow, DEFAULT_WS_URL, normalize_phone
from .session import Session, SessionError, SessionStore
from .transport import Transport


def _safe_account_label(key: str) -> str:
    """برچسب امن برای لاگ: کلیدهای حاوی شماره تلفن هش میشوند."""
    if not isinstance(key, str):
        return "<unknown>"
    if key.startswith("phone:") or any(ch.isdigit() for ch in key.split(":", 1)[-1]):
        digest = hashlib.sha256(key.encode("utf-8", "replace")).hexdigest()[:12]
        return f"<redacted:{digest}>"
    return key

logger = logging.getLogger("badking.hybrid.sessions")


class SessionManagerError(Exception):
    """خطای مدیریت سشن، با راهنما."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message}\n  → {self.hint}" if self.hint else self.message


@dataclass
class AccountInfo:
    """خلاصه وضعیت یک اکانت."""

    key: str
    user_id: int | None
    phone: str
    name: str = ""
    username: str = ""
    valid: bool = False
    balance: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "user_id": self.user_id,
            "phone": self.phone,
            "name": self.name,
            "username": self.username,
            "valid": self.valid,
            "balance": self.balance,
        }


@dataclass
class CreateResult:
    """نتیجه ساخت سشن."""

    ok: bool
    session: Session | None = None
    key: str = ""
    message: str = ""
    needs_code: bool = False
    needs_password: bool = False
    transaction_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "key": self.key,
            "message": self.message,
            "needs_code": self.needs_code,
            "needs_password": self.needs_password,
            "phone": self.session.phone if self.session else "",
        }


@dataclass
class CheckReport:
    """نتیجه بررسی دسته‌ای اکانت‌ها."""

    total: int = 0
    healthy: int = 0
    broken: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"بررسی {self.total} اکانت: "
            f"{self.healthy} سالم، "
            f"{len(self.broken)} خراب، "
            f"{len(self.duplicates)} تکراری"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "healthy": self.healthy,
            "broken": self.broken,
            "duplicates": self.duplicates,
        }


class SessionManager:
    """مدیریت مرکزی اکانت‌های self-bot.

    Args:
        path: فایل ذخیره. پیش‌فرض ``sessions.bks``.
        password: رمز فایل. اگر ``None`` باشد از محیط خوانده می‌شود.
        transport_factory: تابعی که Transport میسازد (برای تست قابل تزریق).
    """

    def __init__(
        self,
        path: str | Path = "sessions.bks",
        *,
        password: str | None = None,
        transport_factory: Callable[[], Transport] | None = None,
    ) -> None:
        self.store = SessionStore(path, password=password)
        self.transport_factory = transport_factory or self._default_transport
        self._pending: dict[str, dict[str, Any]] = {}

    def _default_transport(self) -> Transport:
        """سازنده پیشفرض Transport (با آدرس پیشفرض بله)."""
        return Transport(DEFAULT_WS_URL)

    # ---------- لیست و جستجو ----------

    def list_accounts(self) -> list[AccountInfo]:
        """همه اکانت‌ها."""
        return [
            AccountInfo(
                key=a["key"],
                user_id=a["user_id"],
                phone=a["phone"],
                name=a["name"],
                username=a["username"],
                valid=a["valid"],
            )
            for a in self.store.list_accounts()
        ]

    def search(self, term: str) -> list[AccountInfo]:
        """جستجو بر اساس آیدی، شماره، نام یا یوزرنیم."""
        term = str(term).strip()
        out = []
        for acc in self.list_accounts():
            haystack = {
                str(acc.user_id or ""),
                acc.phone,
                acc.name,
                acc.username,
                acc.key,
            }
            if any(term in value for value in haystack if value):
                out.append(acc)
        return out

    def get(self, key: str) -> Session | None:
        """گرفتن یک session."""
        return self.store.get(key)

    def count(self) -> int:
        return len(self.list_accounts())

    # ---------- ساخت سشن ----------

    async def request_code(self, phone: str) -> CreateResult:
        """قدم اول: ارسال کد SMS.

        بعد از این، ``transaction_hash`` را نگه دار و ``submit_code`` را صدا بزن.
        """
        try:
            normalized = normalize_phone(phone)
        except AuthError as exc:
            return CreateResult(ok=False, message=str(exc))

        # اگر از قبل هست، دوباره نساز. SessionStore کلید را بر اساس
        # user_id میسازد، پس هر دو شکل را چک میکنیم.
        existing = self.store.get(f"phone:{normalized}")
        if existing is None:
            for acc in self.list_accounts():
                if acc.phone == normalized:
                    existing = self.store.get(acc.key)
                    break
        if existing:
            return CreateResult(
                ok=True,
                session=existing,
                key=self.store.key_for(existing),
                message="سشن از قبل وجود دارد",
            )

        transport = self.transport_factory()
        try:
            await transport.connect()
            flow = AuthFlow(transport)
            req = await flow.request_code(normalized)
            self._pending[normalized] = {
                "transaction_hash": req.transaction_hash,
                "phone": normalized,
            }
            return CreateResult(
                ok=True,
                needs_code=True,
                transaction_hash=req.transaction_hash,
                message=f"کد به {normalized} ارسال شد",
            )
        except AuthError as exc:
            return CreateResult(ok=False, message=str(exc))
        except Exception as exc:  # noqa: BLE001
            return CreateResult(ok=False, message=f"خطای اتصال: {exc}")
        finally:
            await transport.close()

    async def submit_code(
        self,
        phone: str,
        code: str,
        *,
        password: str | None = None,
    ) -> CreateResult:
        """قدم دوم: تأیید کد (و در صورت نیاز رمز دومرحله‌ای).

        Args:
            phone: همان شمارهای که ``request_code`` زدی.
            code: کد SMS.
            password: رمز دومرحله‌ای، اگر اکانت آن را فعال کرده باشد.
        """
        normalized = normalize_phone(phone)
        pending = self._pending.get(normalized)
        if not pending:
            return CreateResult(
                ok=False,
                message="اول request_code را صدا بزن",
            )

        transport = self.transport_factory()
        try:
            await transport.connect()
            flow = AuthFlow(transport)

            try:
                result = await flow.sign_in(
                    pending["transaction_hash"], code, phone=normalized
                )
            except AuthError as exc:
                # برخی اکانت‌ها رمز دومرحله‌ای دارند
                if "password" in str(exc).lower() or exc.code in {400, 401}:
                    return CreateResult(
                        ok=False,
                        needs_password=True,
                        transaction_hash=pending["transaction_hash"],
                        message="رمز دومرحله‌ای لازم است",
                    )
                return CreateResult(ok=False, message=str(exc))

            key = self.store.put(result.session)
            self._pending.pop(normalized, None)
            return CreateResult(
                ok=True,
                session=result.session,
                key=key,
                message="سشن ساخته و ذخیره شد",
            )
        except Exception as exc:  # noqa: BLE001
            return CreateResult(ok=False, message=f"خطای اتصال: {exc}")
        finally:
            await transport.close()

    async def create_session(
        self,
        phone: str,
        *,
        code_prompt: Callable[[str], str] | None = None,
        password_prompt: Callable[[str], str] | None = None,
    ) -> CreateResult:
        """جریان کامل تعاملی: شماره → کد → (رمز) → ذخیره.

        مناسب برای رباتی که از کاربر کد میگیرد. ``code_prompt`` را با تابع
        خودت بده تا کد را از پیام کاربر بگیر، نه از input().
        """
        req = await self.request_code(phone)
        if not req.ok:
            return req
        if not req.needs_code:
            return req

        if code_prompt is None:
            code_prompt = input

        code = code_prompt("کد تأیید SMS: ")
        result = await self.submit_code(phone, str(code))

        if result.needs_password:
            if password_prompt is None:
                password_prompt = input
            # رمز دومرحله‌ای همان transaction_hash را میخواهد
            transport = self.transport_factory()
            try:
                await transport.connect()
                flow = AuthFlow(transport)
                from .proto import build, decode, get_str
                from .auth import F_TRANSACTION_HASH

                payload = build(
                    {
                        F_TRANSACTION_HASH: result.transaction_hash,
                        2: str(password_prompt("رمز دومرحله‌ای: ")),
                        3: 1,  # is_jwt
                    }
                )
                frame = await transport.request(payload)
                msg = decode(frame)
                token = get_str(msg, 4)  # F_ACCESS_TOKEN
                if not token:
                    return CreateResult(ok=False, message="رمز دومرحلهای درست نبود")
                session = Session(
                    access_token=token,
                    phone=normalize_phone(phone),
                )
                key = self.store.put(session)
                return CreateResult(ok=True, session=session, key=key, message="سشن ساخته شد")
            except Exception as exc:  # noqa: BLE001
                return CreateResult(ok=False, message=f"خطا: {exc}")
            finally:
                await transport.close()

        return result

    # ---------- حذف ----------

    def remove(self, key: str) -> bool:
        """حذف یک اکانت."""
        return self.store.delete(key)

    def clear(self) -> int:
        """حذف همه اکانت‌ها."""
        count = self.count()
        self.store.save_all({})
        return count

    # ---------- بررسی سلامت ----------

    async def check_all(self, *, remove_broken: bool = False) -> CheckReport:
        """تک تک اکانت‌ها را امتحان میکند.

        Args:
            remove_broken: اکانت خراب/تکراری را حذف هم بکند.
        """
        from .client import SelfBot

        accounts = self.store.load_all()
        report = CheckReport(total=len(accounts))
        seen_ids: set[int] = set()

        for key, session in list(accounts.items()):
            try:
                bot = SelfBot(session=session, transport_factory=self.transport_factory)
                await bot.connect()
                me = await bot.get_me()
                await bot.close()

                uid = int(me.id or 0)
                if uid and uid in seen_ids:
                    report.duplicates.append(key)
                    if remove_broken:
                        self.store.delete(key)
                    continue
                if uid:
                    seen_ids.add(uid)
                report.healthy += 1

            except Exception as exc:  # noqa: BLE001
                # کلید میتواند `phone:<شماره کامل>` باشد — هرگز آن را در لاگ ننویسیم.
                logger.debug("اکانت %s خراب: %s", _safe_account_label(key), exc)
                report.broken.append(key)
                if remove_broken:
                    self.store.delete(key)

        return report

    # ---------- بکاپ / ریستور ----------

    def export_zip(self, path: str | Path, *, include_manifest: bool = True) -> Path:
        """همه سشنها را در یک zip میریزد (جایگزین backup.zip).

        فایل خروجی شامل:
          - sessions.json  — تمام اکانت‌ها (همان فرمت رمزنگاری‌شده store)
          - manifest.json  — تعداد، تاریخ، هش SHA256 (برای تأیید سلامت)
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        raw = self._store_bytes()

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("sessions.bks", raw)
            if include_manifest:
                manifest = {
                    "version": 1,
                    "created_at": time.time(),
                    "count": self.count(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "generator": "badking.SessionManager",
                }
                zf.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )

        path.write_bytes(buffer.getvalue())
        logger.info("بکاپ ساخته شد: %s (%d اکانت)", path, self.count())
        return path

    def import_zip(self, path: str | Path, *, merge: bool = True) -> int:
        """بکاپ را برمیگرداند. تعداد اکانت واردشده را میدهد."""
        path = Path(path)
        if not path.is_file():
            raise SessionManagerError(
                f"فایل بکاپ پیدا نشد: {path}",
                hint="مسیر backup.zip را چک کن.",
            )

        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()

                # پشتیبانی از بکاپهای قدیمی: فایل .bale داخل پوشه sessions/
                if "sessions.bks" in names:
                    raw = zf.read("sessions.bks")
                    if "manifest.json" in names:
                        manifest = json.loads(zf.read("manifest.json"))
                        expected = manifest.get("sha256")
                        if expected and hashlib.sha256(raw).hexdigest() != expected:
                            raise SessionManagerError(
                                "هش بکاپ مطابقت ندارد — فایل دستکاری شده",
                                hint="از بکاپ سالم دیگری استفاده کن.",
                            )
                    return self._load_bytes(raw, merge=merge)

                # بکاپ قدیمی: فایل‌های sessions/*.bale
                bale_files = [
                    n for n in names
                    if n.endswith(".bale") and "__pycache__" not in n
                ]
                if not bale_files:
                    raise SessionManagerError(
                        "در zip نه sessions.bks هست نه فایل .bale",
                        hint="یک بکاپ معتبر BADKING بده.",
                    )

                imported = 0
                for name in bale_files:
                    try:
                        data = json.loads(zf.read(name))
                        session = Session.from_dict(data)
                        self.store.put(session)
                        imported += 1
                    except Exception:  # noqa: BLE001
                        logger.warning("فایل %s قابل خواندن نبود", name)
                return imported

        except zipfile.BadZipFile as exc:
            raise SessionManagerError(
                f"فایل zip خراب است: {exc}",
                hint="مطمئن شو فایل بکاپ کامل است.",
            ) from exc

    def _store_bytes(self) -> bytes:
        """محتوای فایل store را میخواند."""
        if not self.store.path.exists():
            return b""
        return self.store.path.read_bytes()

    def _load_bytes(self, raw: bytes, *, merge: bool) -> int:
        """محتوای بکاپ را بار میکند."""
        tmp = self.store.path.with_suffix(".importing")
        tmp.write_bytes(raw)

        old_path = self.store.path
        try:
            self.store.path = tmp
            incoming = self.store.load_all()
        except Exception as exc:  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            raise SessionManagerError(
                f"بکاپ رمزگذاری نشد: {exc}",
                hint="رمز بکاپ با رمز فعلی یکی است؟ BADKING_SESSION_KEY را چک کن.",
            ) from exc
        finally:
            self.store.path = old_path

        if merge:
            current = self.store.load_all()
            current.update(incoming)
            self.store.save_all(current)
        else:
            self.store.save_all(incoming)

        tmp.unlink(missing_ok=True)
        return len(incoming)

    # ---------- نمایش ----------

    def summary(self) -> str:
        """خلاصه خوانا."""
        accounts = self.list_accounts()
        if not accounts:
            return "هیچ اکنتی ذخیره نشده است."

        lines = [f"{len(accounts)} اکانت ذخیره شده:", ""]
        for acc in accounts[:20]:
            mark = "✓" if acc.valid else "✗"
            lines.append(
                f"  {mark} {acc.phone or acc.key} | id={acc.user_id or '?'} | {acc.name}"
            )
        if len(accounts) > 20:
            lines.append(f"  ... و {len(accounts) - 20} اکانت دیگر")
        return "\n".join(lines)


__all__ = [
    "AccountInfo",
    "CheckReport",
    "CreateResult",
    "SessionManager",
    "SessionManagerError",
]
