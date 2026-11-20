"""تستهای نهایی امنیت: Session Tampering، Permission Bypass، JWT wiring."""

from __future__ import annotations

import pytest

jwt = pytest.importorskip("jwt", reason="PyJWT لازم است")

from badking.hybrid.auth import AuthFlow  # noqa: E402
from badking.hybrid.client import SelfBot, SelfBotError  # noqa: E402
from badking.hybrid.jwt_verify import JWTVerifier  # noqa: E402
from badking.hybrid.proto import build  # noqa: E402
from badking.hybrid.security import PermissionDenied, PermissionPolicy  # noqa: E402
from badking.hybrid.session import Session, SessionError, SessionStore  # noqa: E402

KEY = "a-32-byte-secret-key-for-tests-1234"


# ---------- Session tampering ----------

def test_session_tampering_detected(tmp_path):
    """دستکاری فایل session رمزنگاریشده شناسایی میشود."""
    path = tmp_path / "s.bks"
    store = SessionStore(path, password="strong-pass")
    store.put(Session(access_token="token", user_id=1))
    blob = bytearray(path.read_bytes())
    # یک بایت از بدنه را عوض میکنیم
    blob[-1] ^= 0xFF
    path.write_bytes(bytes(blob))
    with pytest.raises(SessionError):
        SessionStore(path, password="strong-pass").load_all()


def test_session_wrong_password_rejected(tmp_path):
    path = tmp_path / "s.bks"
    SessionStore(path, password="right").put(Session(user_id=1))
    with pytest.raises(SessionError):
        SessionStore(path, password="wrong").load_all()


def test_session_no_key_rejected(tmp_path):
    path = tmp_path / "s.bks"
    SessionStore(path, password="right").put(Session(user_id=1))
    with pytest.raises(SessionError):
        SessionStore(path, password=None).load_all()


# ---------- Permission bypass ----------

@pytest.mark.asyncio
async def test_permission_bypass_blocked():
    """حتی با transport دستی، متد حساس بدون مجوز رد میشود."""
    bot = SelfBot(session=Session(access_token="t", user_id=1))
    # transport دستی نصب میکنیم تا چک مجوز دور زده نشود
    class T:
        connected = True

        async def request(self, *a, **k):
            return build({})

    bot._transport = T()
    with pytest.raises(PermissionDenied):
        await bot.call("messaging.SendMessage", peer={}, content={})


@pytest.mark.asyncio
async def test_raw_call_permission_bypass_blocked():
    bot = SelfBot(session=Session(access_token="t", user_id=1))

    class T:
        connected = True

        async def request(self, *a, **k):
            return build({})

    bot._transport = T()
    with pytest.raises(PermissionDenied):
        await bot.raw_call("messaging.SendMessage", {1: b"x"})


def test_dangerous_rpc_requires_explicit_optin():
    policy = PermissionPolicy(allow=frozenset({"send_messages"}))
    with pytest.raises(PermissionDenied):
        policy.check("messaging.DeleteMessage")
    full = PermissionPolicy.full()
    full.check("messaging.DeleteMessage")  # بدون خطا


# ---------- JWT wiring in SelfBot.connect ----------

@pytest.mark.asyncio
async def test_selfbot_connect_verifies_jwt():
    """توکن نامعتبر هنگام connect رد میشود (مسیر مصرف واقعی)."""
    import time

    verifier = JWTVerifier(key=KEY, algorithms=("HS256",))
    # exp معتبر است ولی امضا با کلید دیگریست → is_valid True ولی verifier رد میکند
    bad = jwt.encode(
        {"exp": time.time() + 60},
        "another-32-byte-secret-key-for-tests",
        algorithm="HS256",
    )
    bot = SelfBot(session=Session(access_token=bad, user_id=1), jwt_verifier=verifier)
    with pytest.raises(SelfBotError, match="نامعتبر"):
        await bot.connect()


@pytest.mark.asyncio
async def test_selfbot_connect_without_verifier_legacy():
    """Regression: بدون verifier رفتار قدیمی حفظ میشود."""
    bot = SelfBot(session=Session(access_token="legacy", user_id=1))

    class T:
        connected = True
        on_update = None

        async def connect(self):
            return None

        async def request(self, *a, **k):
            return build({})

    bot.transport_factory = lambda: T()
    await bot.connect()
    assert bot.connected


# ---------- AuthFlow refresh verifies ----------

@pytest.mark.asyncio
async def test_authflow_refresh_verifies_jwt():
    verifier = JWTVerifier(key=KEY, algorithms=("HS256",))
    bad = jwt.encode({"exp": 1}, KEY, algorithm="HS256")

    class T:
        async def request(self, payload):
            return build({4: bad})

    flow = AuthFlow(T(), jwt_verifier=verifier)
    with pytest.raises(Exception, match="نامعتبر"):
        await flow.refresh(Session(refresh_token="r"))


# ---------- Regression: no secret in errors ----------

def test_permission_error_has_no_token():
    err = PermissionDenied("messaging.SendMessage", "send_messages", ())
    assert "token" not in str(err).lower()
