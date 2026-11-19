"""تست موتور تاب‌آوری و سلسله‌مراتب خطاها — همه آفلاین."""

from __future__ import annotations

import asyncio

import pytest

from badking.core.errors import (
    BADKINGError,
    BadRequestError,
    BaleError,
    ChatNotFoundError,
    CircuitOpenError,
    ConnectionError,
    DecodeError,
    FloodWaitError,
    MediaError,
    MessageTooLongError,
    NetworkError,
    NotAdminError,
    ProtocolError,
    RateLimitError,
    SessionError,
    StopPropagation,
    StorageError,
    TimeoutError_,
    UnauthorizedError,
    ValidationError,
    error_for_code,
    format_exception,
    raise_for_response,
)
from badking.resilience import (
    Backoff,
    CircuitBreaker,
    CircuitState,
    RequestQueue,
    ResilientCaller,
    RetryPolicy,
)


# ---------- سلسله‌مراتب ----------

class TestErrorHierarchy:
    def test_root(self):
        assert issubclass(UnauthorizedError, BADKINGError)
        assert issubclass(NetworkError, ConnectionError)
        assert issubclass(DecodeError, ProtocolError)
        assert issubclass(NotAdminError, BADKINGError)

    def test_legacy_aliases(self):
        assert BaleError is BADKINGError
        assert issubclass(BadRequestError, ValidationError)

    def test_stop_propagation_is_not_an_error(self):
        # کنترل جریان است، نه خطا
        assert not issubclass(StopPropagation, BADKINGError)

    def test_every_error_has_code(self):
        for cls in (
            BADKINGError, UnauthorizedError, NetworkError, RateLimitError,
            ValidationError, MediaError, SessionError, StorageError,
            ProtocolError, TimeoutError_, ChatNotFoundError,
        ):
            assert cls.error_code
            assert cls.error_code.isupper()

    def test_hint_present(self):
        exc = UnauthorizedError("توکن غلط")
        assert exc.hint
        assert "توکن" in exc.hint

    def test_custom_hint_overrides(self):
        exc = NetworkError("x", hint="راه‌حل من")
        assert exc.hint == "راه‌حل من"

    def test_str_includes_hint(self):
        exc = RateLimitError("زیاد")
        assert "→" in str(exc)

    def test_str_includes_method(self):
        exc = RateLimitError("زیاد", method="SendMessage")
        assert "SendMessage" in str(exc)

    def test_diagnose(self):
        exc = RateLimitError("زیاد", code=429, method="SendMessage",
                             parameters={"retry_after": 5})
        report = exc.diagnose()
        assert "RATE_LIMITED" in report
        assert "429" in report
        assert "SendMessage" in report
        assert "راه‌حل" in report

    def test_retry_after(self):
        exc = RateLimitError("x", parameters={"retry_after": 7})
        assert exc.retry_after == 7.0

    def test_retry_after_none(self):
        assert RateLimitError("x").retry_after is None

    def test_retryable_flags(self):
        assert NetworkError("x").retryable is True
        assert TimeoutError_("x").retryable is True
        assert RateLimitError("x").retryable is True
        assert CircuitOpenError("x").retryable is True
        assert ValidationError("x").retryable is False
        assert UnauthorizedError("x").retryable is False

    def test_repr(self):
        assert "RateLimitError" in repr(RateLimitError("x", code=429))


# ---------- نگاشت کد ----------

class TestErrorMapping:
    def test_ok_returns_result(self):
        assert raise_for_response({"ok": True, "result": {"id": 1}}) == {"id": 1}

    def test_401(self):
        with pytest.raises(UnauthorizedError):
            raise_for_response({"ok": False, "error_code": 401, "description": "unauthorized"})

    def test_429(self):
        with pytest.raises(RateLimitError):
            raise_for_response({"ok": False, "error_code": 429, "description": "too many"})

    def test_400(self):
        with pytest.raises(ValidationError):
            raise_for_response({"ok": False, "error_code": 400, "description": "bad"})

    def test_403(self):
        with pytest.raises(NotAdminError):
            raise_for_response(
                {"ok": False, "error_code": 403, "description": "not enough rights"}
            )

    def test_flood_detected_by_text(self):
        with pytest.raises(FloodWaitError):
            raise_for_response(
                {"ok": False, "error_code": 500, "description": "FLOOD_WAIT_30"}
            )

    def test_chat_not_found_by_text(self):
        with pytest.raises(ChatNotFoundError):
            raise_for_response(
                {"ok": False, "error_code": 400, "description": "chat not found"}
            )

    def test_message_too_long(self):
        with pytest.raises(MessageTooLongError):
            raise_for_response(
                {"ok": False, "error_code": 400, "description": "message is too long"}
            )

    def test_unknown_code_falls_back(self):
        with pytest.raises(BADKINGError):
            raise_for_response({"ok": False, "error_code": 999, "description": "?"})

    def test_error_for_code(self):
        assert error_for_code(401) is UnauthorizedError
        assert error_for_code(None) is BADKINGError
        assert error_for_code(12345) is BADKINGError

    def test_method_recorded(self):
        with pytest.raises(UnauthorizedError) as info:
            raise_for_response({"ok": False, "error_code": 401}, method="GetMe")
        assert info.value.method == "GetMe"


# ---------- پاک‌سازی توکن ----------

class TestFormatException:
    def test_token_redacted(self):
        exc = BADKINGError("خطا با توکن 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw")
        out = format_exception(exc)
        assert "<TOKEN>" in out
        assert "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" not in out

    def test_hex_redacted(self):
        exc = BADKINGError("کلید " + "a" * 40)
        assert "<HEX_SECRET>" in format_exception(exc)

    def test_plain_exception(self):
        out = format_exception(ValueError("مشکل"))
        assert "ValueError" in out
        assert "مشکل" in out

    def test_traceback_optional(self):
        try:
            raise ValueError("x")
        except ValueError as exc:
            without = format_exception(exc)
            with_tb = format_exception(exc, include_traceback=True)
        assert "Traceback" not in without
        assert "Traceback" in with_tb


# ---------- backoff ----------

class TestBackoff:
    def test_fixed(self):
        p = RetryPolicy(base_delay=1.0, backoff=Backoff.FIXED, jitter=0)
        assert p.delay_for(1) == 1.0
        assert p.delay_for(5) == 1.0

    def test_linear(self):
        p = RetryPolicy(base_delay=1.0, backoff=Backoff.LINEAR, jitter=0)
        assert p.delay_for(1) == 1.0
        assert p.delay_for(3) == 3.0

    def test_exponential(self):
        p = RetryPolicy(base_delay=1.0, backoff=Backoff.EXPONENTIAL, jitter=0)
        assert p.delay_for(1) == 1.0
        assert p.delay_for(2) == 2.0
        assert p.delay_for(4) == 8.0

    def test_max_delay_caps(self):
        p = RetryPolicy(base_delay=1.0, max_delay=5.0, jitter=0)
        assert p.delay_for(10) == 5.0

    def test_jitter_adds(self):
        p = RetryPolicy(base_delay=1.0, backoff=Backoff.FIXED, jitter=0.5)
        for _ in range(20):
            d = p.delay_for(1)
            assert 1.0 <= d <= 1.5


# ---------- تلاش مجدد ----------

class TestRetryPolicy:
    def test_succeeds_first_try(self):
        async def ok():
            return 1

        assert asyncio.get_event_loop().run_until_complete(
            RetryPolicy(attempts=3, base_delay=0).run(ok)
        ) == 1

    def test_retries_then_succeeds(self):
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise NetworkError("قطعی")
            return "ok"

        result = asyncio.get_event_loop().run_until_complete(
            RetryPolicy(attempts=5, base_delay=0.001).run(flaky)
        )
        assert result == "ok"
        assert calls["n"] == 3

    def test_gives_up_after_attempts(self):
        calls = {"n": 0}

        async def always():
            calls["n"] += 1
            raise NetworkError("همیشه")

        with pytest.raises(NetworkError):
            asyncio.get_event_loop().run_until_complete(
                RetryPolicy(attempts=3, base_delay=0.001).run(always)
            )
        assert calls["n"] == 3

    def test_does_not_retry_validation_error(self):
        calls = {"n": 0}

        async def bad():
            calls["n"] += 1
            raise ValidationError("ورودی غلط")

        with pytest.raises(ValidationError):
            asyncio.get_event_loop().run_until_complete(
                RetryPolicy(attempts=5, base_delay=0.001).run(bad)
            )
        assert calls["n"] == 1

    def test_does_not_retry_auth_error(self):
        calls = {"n": 0}

        async def bad():
            calls["n"] += 1
            raise UnauthorizedError("توکن غلط")

        with pytest.raises(UnauthorizedError):
            asyncio.get_event_loop().run_until_complete(
                RetryPolicy(attempts=5, base_delay=0.001).run(bad)
            )
        assert calls["n"] == 1

    def test_respects_retry_after(self):
        calls = {"n": 0}

        async def limited():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RateLimitError("صبر", parameters={"retry_after": 0.01})
            return "ok"

        result = asyncio.get_event_loop().run_until_complete(
            RetryPolicy(attempts=3, base_delay=10.0, max_delay=0.05).run(limited)
        )
        assert result == "ok"

    def test_on_retry_callback(self):
        seen = []

        async def flaky():
            if not seen:
                seen.append("x")
                raise NetworkError("x")
            return 1

        policy = RetryPolicy(
            attempts=3, base_delay=0.001,
            on_retry=lambda n, e, d: seen.append((n, type(e).__name__)),
        )
        asyncio.get_event_loop().run_until_complete(policy.run(flaky))
        assert (1, "NetworkError") in seen

    def test_should_retry_logic(self):
        p = RetryPolicy()
        assert p.should_retry(NetworkError("x")) is True
        assert p.should_retry(ValidationError("x")) is False
        assert p.should_retry(ValueError("x")) is True

    def test_give_up_on_overrides(self):
        p = RetryPolicy(give_up_on=(NetworkError,))
        assert p.should_retry(NetworkError("x")) is False


# ---------- مدارشکن ----------

class TestCircuitBreaker:
    def test_starts_closed(self):
        assert CircuitBreaker().state is CircuitState.CLOSED

    def test_opens_after_threshold(self):
        b = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            b.record_failure()
        assert b.state is CircuitState.OPEN

    def test_not_open_below_threshold(self):
        b = CircuitBreaker(failure_threshold=3)
        b.record_failure()
        b.record_failure()
        assert b.state is CircuitState.CLOSED

    def test_success_resets_failures(self):
        b = CircuitBreaker(failure_threshold=3)
        b.record_failure()
        b.record_failure()
        b.record_success()
        b.record_failure()
        assert b.state is CircuitState.CLOSED

    def test_open_raises(self):
        b = CircuitBreaker(failure_threshold=1, cooldown=60)

        async def fail():
            raise NetworkError("x")

        async def anything():
            return 1

        with pytest.raises(NetworkError):
            asyncio.get_event_loop().run_until_complete(b.call(fail))

        with pytest.raises(CircuitOpenError):
            asyncio.get_event_loop().run_until_complete(b.call(anything))

    @staticmethod
    def _wait_for_half_open(breaker, timeout=2.0):
        """صبر می‌کند تا مدار به half-open برسد.

        time.sleep با مقدار ثابت روی ویندوز شکننده است: دقت ساعت سیستم
        ۱۵.۶ میلی‌ثانیه است، پس sleep(0.02) ممکن است واقعاً ۰.۰۲ ثانیه
        نباشد. شرط را می‌پاییم، نه زمان را.
        """
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if breaker.state is CircuitState.HALF_OPEN:
                return True
            time.sleep(0.005)
        return False

    def test_half_open_after_cooldown(self):
        b = CircuitBreaker(failure_threshold=1, cooldown=0.02)
        b.record_failure()
        assert b.state is CircuitState.OPEN
        assert self._wait_for_half_open(b), "مدار به half-open نرسید"

    def test_half_open_closes_on_success(self):
        b = CircuitBreaker(failure_threshold=1, cooldown=0.02, success_threshold=1)
        b.record_failure()
        assert self._wait_for_half_open(b)
        b.record_success()
        assert b.state is CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self):
        b = CircuitBreaker(failure_threshold=1, cooldown=0.02)
        b.record_failure()
        assert self._wait_for_half_open(b)
        b.record_failure()
        assert b.state is CircuitState.OPEN

    def test_reset(self):
        b = CircuitBreaker(failure_threshold=1)
        b.record_failure()
        b.reset()
        assert b.state is CircuitState.CLOSED

    def test_call_success(self):
        b = CircuitBreaker()

        async def ok():
            return 42

        assert asyncio.get_event_loop().run_until_complete(b.call(ok)) == 42

    def test_is_open_property(self):
        b = CircuitBreaker(failure_threshold=1)
        assert b.is_open is False
        b.record_failure()
        assert b.is_open is True


# ---------- صف ----------

class TestRequestQueue:
    def test_runs_task(self):
        q = RequestQueue(concurrency=2)

        async def work(x):
            return x * 2

        assert asyncio.get_event_loop().run_until_complete(q.submit(work, 21)) == 42

    def test_invalid_concurrency(self):
        with pytest.raises(ValueError):
            RequestQueue(concurrency=0)

    def test_invalid_rate(self):
        with pytest.raises(ValueError):
            RequestQueue(rate=-1)

    def test_pending_back_to_zero(self):
        q = RequestQueue(concurrency=2)

        async def work():
            return 1

        asyncio.get_event_loop().run_until_complete(q.submit(work))
        assert q.pending == 0

    def test_pending_decrements_on_error(self):
        q = RequestQueue(concurrency=2)

        async def boom():
            raise ValueError("x")

        with pytest.raises(ValueError):
            asyncio.get_event_loop().run_until_complete(q.submit(boom))
        assert q.pending == 0

    def test_max_pending_enforced(self):
        q = RequestQueue(concurrency=1, max_pending=1)

        async def slow():
            await asyncio.sleep(0.05)
            return 1

        async def scenario():
            first = asyncio.ensure_future(q.submit(slow))
            await asyncio.sleep(0.01)
            with pytest.raises(BADKINGError):
                await q.submit(slow)
            await first

        asyncio.get_event_loop().run_until_complete(scenario())

    def test_concurrency_limit_respected(self):
        q = RequestQueue(concurrency=2)
        active = {"now": 0, "peak": 0}

        async def track():
            active["now"] += 1
            active["peak"] = max(active["peak"], active["now"])
            await asyncio.sleep(0.01)
            active["now"] -= 1
            return 1

        async def scenario():
            await asyncio.gather(*[q.submit(track) for _ in range(10)])

        asyncio.get_event_loop().run_until_complete(scenario())
        assert active["peak"] <= 2


# ---------- ترکیب ----------

class TestResilientCaller:
    def test_runs(self):
        caller = ResilientCaller(
            queue=RequestQueue(concurrency=2),
            breaker=CircuitBreaker(failure_threshold=5),
            policy=RetryPolicy(attempts=2, base_delay=0.001),
        )

        async def work(x):
            return x + 1

        assert asyncio.get_event_loop().run_until_complete(caller(work, 1)) == 2

    def test_retries_inside(self):
        caller = ResilientCaller(
            policy=RetryPolicy(attempts=3, base_delay=0.001),
        )
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise NetworkError("x")
            return "ok"

        assert asyncio.get_event_loop().run_until_complete(caller(flaky)) == "ok"
        assert calls["n"] == 2

    def test_breaker_counts_final_failure_once(self):
        # تلاش مجدد داخل مدارشکن است، پس ۳ تلاش = ۱ شکست
        breaker = CircuitBreaker(failure_threshold=2)
        caller = ResilientCaller(
            breaker=breaker,
            policy=RetryPolicy(attempts=3, base_delay=0.001),
        )

        async def always():
            raise NetworkError("x")

        with pytest.raises(NetworkError):
            asyncio.get_event_loop().run_until_complete(caller(always))

        assert breaker.state is CircuitState.CLOSED
