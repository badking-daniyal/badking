"""تستهای واقعی JWT verification — با PyJWT، بدون رمزنگاری دستساز."""

from __future__ import annotations

import time

import pytest

jwt = pytest.importorskip("jwt", reason="PyJWT لازم است")

from badking.hybrid.auth import AuthError, AuthFlow  # noqa: E402
from badking.hybrid.jwt_verify import (  # noqa: E402
    JWTNotConfigured,
    JWTVerificationFailed,
    JWTVerifier,
    make_verifier,
)

# کلید ۳۲ بایتی — از هشدار InsecureKeyLength جلوگیری میکند.
KEY = "a-32-byte-secret-key-for-tests-1234"
ALGOS = ("HS256",)


def _token(**claims):
    base = {"exp": time.time() + 60, "iss": "bale", "aud": "app", "sub": "1"}
    base.update(claims)
    return jwt.encode(base, KEY, algorithm="HS256")


def _verifier(**kwargs):
    opts = dict(key=KEY, algorithms=ALGOS, issuer="bale", audience="app")
    opts.update(kwargs)
    return JWTVerifier(**opts)


# ---------- JWT Valid ----------

def test_jwt_valid():
    payload = _verifier().verify(_token())
    assert payload["sub"] == "1"
    assert payload["iss"] == "bale"


def test_make_verifier_without_key_is_none():
    assert make_verifier(None) is None


def test_make_verifier_with_key():
    assert isinstance(make_verifier(KEY), JWTVerifier)


# ---------- Invalid signature ----------

def test_jwt_invalid_signature():
    token = jwt.encode(
        {"exp": time.time() + 60, "iss": "bale", "aud": "app"},
        "another-32-byte-secret-key-for-tests",
        algorithm="HS256",
    )
    with pytest.raises(JWTVerificationFailed):
        _verifier().verify(token)


# ---------- Expired / Not before ----------

def test_jwt_expired():
    with pytest.raises(JWTVerificationFailed):
        _verifier().verify(_token(exp=time.time() - 10))


def test_jwt_not_yet_valid():
    with pytest.raises(JWTVerificationFailed):
        _verifier().verify(_token(nbf=time.time() + 60))


def test_jwt_leeway_allows_small_clock_skew():
    # 2 ثانیه عقبتر از حالا، با leeway=5 باید پذیرفته شود
    payload = _verifier(leeway=5).verify(_token(exp=time.time() - 2))
    assert payload["sub"] == "1"


# ---------- Algorithm restrictions ----------

def test_jwt_invalid_algorithm():
    long_key = "a-64-byte-secret-key-for-HS512-tests-123456789012345678901234567890"
    token = jwt.encode(
        {"exp": time.time() + 60, "iss": "bale", "aud": "app"},
        long_key,
        algorithm="HS512",
    )
    with pytest.raises(JWTVerificationFailed):
        _verifier(algorithms=("HS256",)).verify(token)


def test_jwt_algorithm_confusion_rejected():
    # توکن HS256 امضاشده با همان کلید، ولی verifier فقط RS256 مجاز میکند
    token = _token()
    with pytest.raises(JWTVerificationFailed):
        _verifier(algorithms=("RS256",)).verify(token)


def test_jwt_none_algorithm_config_rejected():
    with pytest.raises(JWTNotConfigured):
        JWTVerifier(key=KEY, algorithms=("none",))


def test_jwt_none_algorithm_token_rejected():
    token = jwt.encode(
        {"exp": time.time() + 60, "iss": "bale", "aud": "app"},
        key="",
        algorithm="none",
    )
    with pytest.raises(JWTVerificationFailed):
        _verifier().verify(token)


def test_jwt_unknown_algorithm_config_rejected():
    with pytest.raises(JWTNotConfigured):
        JWTVerifier(key=KEY, algorithms=("XX999",))


# ---------- Malformed / missing claims ----------

@pytest.mark.parametrize("bad", ["", "abc", "a.b", "a.b.c.d", "..", "!!!.!!!.!!!"])
def test_jwt_malformed_rejected(bad):
    with pytest.raises(JWTVerificationFailed):
        _verifier().verify(bad)


def test_jwt_missing_exp_rejected():
    token = jwt.encode(
        {"iss": "bale", "aud": "app"},
        KEY,
        algorithm="HS256",
    )
    with pytest.raises(JWTVerificationFailed):
        _verifier().verify(token)


def test_jwt_wrong_issuer_rejected():
    with pytest.raises(JWTVerificationFailed):
        _verifier().verify(_token(iss="evil"))


def test_jwt_wrong_audience_rejected():
    with pytest.raises(JWTVerificationFailed):
        _verifier().verify(_token(aud="evil"))


def test_jwt_custom_required_claim():
    token = jwt.encode(
        {"exp": time.time() + 60, "iss": "bale", "aud": "app"},
        KEY,
        algorithm="HS256",
    )
    with pytest.raises(JWTVerificationFailed):
        _verifier(require=("exp", "sub")).verify(token)


# ---------- No secret leakage ----------

def test_jwt_error_message_has_no_token():
    token = _token(exp=time.time() - 10)
    with pytest.raises(JWTVerificationFailed) as exc:
        _verifier().verify(token)
    msg = str(exc.value)
    assert token not in msg
    assert "eyJ" not in msg


# ---------- Integration: AuthFlow really verifies ----------

class _FakeTransport:
    def __init__(self, token: str):
        self.token = token

    async def request(self, payload):
        from badking.hybrid.proto import build

        # ساخت پیام با فیلد access_token=4
        return build({4: self.token, 6: 123})


@pytest.mark.asyncio
async def test_authflow_sign_in_verifies_token():
    bad_token = jwt.encode(
        {"exp": time.time() - 60, "iss": "bale", "aud": "app"},
        KEY,
        algorithm="HS256",
    )
    flow = AuthFlow(_FakeTransport(bad_token), jwt_verifier=_verifier())
    with pytest.raises(AuthError, match="نامعتبر"):
        await flow.sign_in("tx", "1234")


@pytest.mark.asyncio
async def test_authflow_sign_in_accepts_valid_token():
    good = _token()
    flow = AuthFlow(_FakeTransport(good), jwt_verifier=_verifier())
    result = await flow.sign_in("tx", "1234")
    assert result.session.access_token == good


@pytest.mark.asyncio
async def test_authflow_without_verifier_keeps_legacy_behavior():
    # Regression: رفتار قدیمی بدون verifier تغییر نکرده است
    token = "not-a-jwt-but-legacy-accepts"
    flow = AuthFlow(_FakeTransport(token))
    result = await flow.sign_in("tx", "1234")
    assert result.session.access_token == token
