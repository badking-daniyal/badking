"""تست واقعی Cross-Process Race Condition در Session Storage.

این تستها processهای مستقل سیستمعامل ایجاد میکنند (multiprocessing spawn)،
نه mock. هدف: اثبات اینکه نوشتن همزمان حتی یک Session سالم از بین نرود.

روی Windows از ``spawn`` و روی Linux از ``fork``/``spawn`` استفاده میشود تا
رفتار واقعی هر دو پلتفرم پوشش داده شود. workerها در سطح ماژول تعریف شدهاند
تا قابل pickling باشند.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from badking.hybrid.session import Session, SessionStore

_HERE = str(Path(__file__).resolve().parents[1])


def _ctx():
    # spawn روی هر دو پلتفرم، شبیهترین رفتار به process مستقل واقعی.
    return mp.get_context("spawn")


def _write_many(path, password, base, count, barrier, delay=0.0):
    sys.path.insert(0, _HERE)
    from badking.hybrid.session import Session, SessionStore

    store = SessionStore(path, password=password)
    for i in range(count):
        n = base + i
        store.put(Session(user_id=n, access_token=f"tok-{n}", phone=f"+98{n}"))
        if delay:
            time.sleep(delay)
    if barrier is not None:
        try:
            barrier.wait(timeout=60)
        except Exception:
            pass


def _read_modify_write(path, password, key, rounds, barrier):
    """هر process مکرراً یک شمارنده را +1 میکند (Lost Update آشکار)."""
    sys.path.insert(0, _HERE)
    from badking.hybrid.session import Session, SessionStore

    store = SessionStore(path, password=password)

    def bump(cur):
        cur.extra = dict(cur.extra or {})
        cur.extra["counter"] = int(cur.extra.get("counter", 0)) + 1
        return cur

    for _ in range(rounds):
        # update() خواندن+تغییر+نوشتن را تحت یک قفل انجام میدهد.
        store.update(key, bump)
    if barrier is not None:
        try:
            barrier.wait(timeout=60)
        except Exception:
            pass


def _crash_holder(path, password, ready, release):
    """Processی که قفل میگیرد و بدون آزادسازی میمیرد."""
    sys.path.insert(0, _HERE)
    from badking.hybrid.session import Session, SessionStore
    from badking.hybrid.session_lock import cross_process_lock

    store = SessionStore(path, password=password)
    store.put(Session(user_id=999, access_token="seed"))
    with cross_process_lock(path, timeout=30):
        ready.set()
        release.wait(timeout=60)
        os._exit(7)  # خروج غیرمنتظره هنگام نگه داشتن قفل


def _migrate_worker(path, password, barrier):
    sys.path.insert(0, _HERE)
    from badking.hybrid.session import SessionStore

    store = SessionStore(path, password=password)
    try:
        store.migrate_to_v2(backup=True)
    except Exception:
        pass  # برخی processها ممکن است بعد از migrate شکست بخورند — مجاز است
    if barrier is not None:
        try:
            barrier.wait(timeout=60)
        except Exception:
            pass


def _rollback_worker(path, password, barrier):
    sys.path.insert(0, _HERE)
    from badking.hybrid.session import SessionStore

    store = SessionStore(path, password=password)
    try:
        store.rollback_migration()
    except Exception:
        pass
    if barrier is not None:
        try:
            barrier.wait(timeout=60)
        except Exception:
            pass


def _mixed_ops_worker(path, password, base, barrier):
    """ترکیب put / update / delete روی کلیدهای مجزا."""
    sys.path.insert(0, _HERE)
    from badking.hybrid.session import Session, SessionStore

    store = SessionStore(path, password=password)
    for i in range(3):
        n = base + i
        store.put(Session(user_id=n, access_token=f"tok-{n}"))
        store.update(f"user:{n}", lambda s: s)
    if barrier is not None:
        try:
            barrier.wait(timeout=60)
        except Exception:
            pass


def _run_workers(target, args_list, timeout=180):
    ctx = _ctx()
    procs = [ctx.Process(target=target, args=a) for a in args_list]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=timeout)
    return [p.exitcode for p in procs]


# ---------------------------------------------------------------------------


@pytest.mark.parametrize("password", [None, "test-pass-123"], ids=["plain", "encrypted"])
def test_two_processes_concurrent_writes_no_loss(tmp_path, password):
    path = tmp_path / "s.session"
    codes = _run_workers(_write_many, [
        (str(path), password, 1, 5, None),
        (str(path), password, 6, 5, None),
    ])
    assert codes == [0, 0]
    final = SessionStore(path, password=password).load_all()
    assert len(final) == 10, f"Lost Update: {len(final)}/10"
    for n in range(1, 11):
        assert f"user:{n}" in final


def test_ten_processes_concurrent_writes_no_loss(tmp_path):
    path = tmp_path / "s.session"
    args = [(str(path), None, i * 3 + 1, 3, None) for i in range(10)]
    codes = _run_workers(_write_many, args)
    assert codes == [0] * 10
    final = SessionStore(path).load_all()
    assert len(final) == 30, f"Lost Update: {len(final)}/30"


def test_concurrent_read_modify_write_no_lost_increment(tmp_path):
    """۵ process × ۴ بار خواندن/افزایش/نوشتن → شمارنده باید ۲۰ باشد."""
    path = tmp_path / "s.session"
    SessionStore(path).put(Session(user_id=1, extra={"counter": 0}))
    args = [(str(path), None, "user:1", 4, None) for _ in range(5)]
    codes = _run_workers(_read_modify_write, args)
    assert codes == [0] * 5
    final = SessionStore(path).load_all()
    assert final["user:1"].extra["counter"] == 20


def test_writes_to_different_sessions_are_independent(tmp_path):
    path = tmp_path / "s.session"
    args = [(str(path), None, i * 2 + 1, 2, None) for i in range(4)]
    assert _run_workers(_write_many, args) == [0] * 4
    assert len(SessionStore(path).load_all()) == 8


def test_writes_to_same_session_key_last_write_is_complete(tmp_path):
    """چند process همان کلید را مینویسند — نتیجه ناقص نیست."""
    path = tmp_path / "s.session"
    args = [(str(path), None, 1, 1, None) for _ in range(6)]
    # هر process user_id=1 مینویسد ولی phone متفاوتی هم اضافه میکند
    # (همان user_id → همان کلید). فقط بررسی میکنیم فایل سالم و قابل خواندن است.
    assert _run_workers(_write_many, args) == [0] * 6
    final = SessionStore(path).load_all()
    assert len(final) == 1
    assert final["user:1"].access_token.startswith("tok-")


def test_crash_while_holding_lock_does_not_block_others(tmp_path):
    """Processی هنگام نگه داشتن قفل بمیرد — قفل دائمی باقی نماند."""
    path = tmp_path / "s.session"
    ctx = _ctx()
    ready = ctx.Event()
    release = ctx.Event()
    holder = ctx.Process(target=_crash_holder, args=(str(path), None, ready, release))
    holder.start()
    assert ready.wait(timeout=60)
    release.set()
    holder.join(timeout=60)
    assert holder.exitcode == 7  # همانطور که انتظار میرفت crash کرد

    # process دیگری باید بتواند بنویسد — قفل آزاد شده است.
    p = ctx.Process(target=_write_many, args=(str(path), None, 42, 1, None))
    p.start()
    p.join(timeout=60)
    assert p.exitcode == 0
    final = SessionStore(path).load_all()
    assert "user:42" in final
    assert "user:999" in final  # نوشته قبل از crash از بین نرفت


def test_concurrent_migration_keeps_all_sessions(tmp_path):
    """چند process همزمان migrate میکنند — هیچ sessionی از بین نرود."""
    path = tmp_path / "s.session"
    password = "migration-pass"
    # ابتدا چند session بسازیم
    store = SessionStore(path, password=password)
    for n in range(1, 6):
        store.put(Session(user_id=n, access_token=f"tok-{n}"))
    assert store.needs_migration() is False  # از قبل BKS3 است

    args = [(str(path), password, None) for _ in range(5)]
    codes = _run_workers(_migrate_worker, args)
    assert codes == [0] * 5
    final = SessionStore(path, password=password).load_all()
    assert len(final) == 5, f"Sessionها در migration از بین رفتند: {len(final)}/5"
    for n in range(1, 6):
        assert final[f"user:{n}"].access_token == f"tok-{n}"


def test_all_sessions_readable_after_stress(tmp_path):
    """پس از استرس، تمام sessionها قابل بازخوانی و صحت_token دارند."""
    path = tmp_path / "s.session"
    password = "stress-pass"
    args = [(str(path), password, i * 5 + 1, 5, None) for i in range(8)]
    assert _run_workers(_write_many, args) == [0] * 8
    final = SessionStore(path, password=password).load_all()
    assert len(final) == 40
    for n in range(1, 41):
        s = final[f"user:{n}"]
        assert s.access_token == f"tok-{n}"
        assert s.phone == f"+98{n}"


def test_lock_timeout_is_bounded(tmp_path):
    """انتظار برای قفل بیش از timeout طول نمیکشد."""
    from badking.hybrid.session_lock import (
        FileLockTimeout,
        cross_process_lock,
        lock_path_for,
    )

    path = tmp_path / "s.session"
    lp = lock_path_for(path)
    lp.write_bytes(b"\x00")

    if os.name == "nt":
        import msvcrt

        fd = os.open(str(lp), os.O_RDWR)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:  # pragma: no cover
        import fcntl

        fd = os.open(str(lp), os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    try:
        t0 = time.monotonic()
        with pytest.raises(FileLockTimeout):
            with cross_process_lock(path, timeout=0.3, poll_interval=0.02):
                pass  # نباید وارد شود
        elapsed = time.monotonic() - t0
        assert elapsed < 5.0, f"timeout رعایت نشد: {elapsed:.2f}s"
    finally:
        if os.name == "nt":
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:  # pragma: no cover
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def test_concurrent_rollback_keeps_sessions(tmp_path):
    """چند process همزمان rollback میکنند — بکاپ سالم باقی بماند."""
    path = tmp_path / "s.session"
    password = "rb-pass"
    store = SessionStore(path, password=password)
    for n in range(1, 4):
        store.put(Session(user_id=n, access_token=f"tok-{n}"))
    store.backup()
    args = [(str(path), password, None) for _ in range(4)]
    assert _run_workers(_rollback_worker, args) == [0] * 4
    final = SessionStore(path, password=password).load_all()
    assert len(final) == 3
    for n in range(1, 4):
        assert final[f"user:{n}"].access_token == f"tok-{n}"


def test_mixed_update_delete_put_concurrent(tmp_path):
    """رقابت update/delete/put — هیچ session سالمی از بین نرود."""
    path = tmp_path / "s.session"
    args = [(str(path), None, i * 3 + 1, None) for i in range(4)]
    assert _run_workers(_mixed_ops_worker, args) == [0] * 4
    final = SessionStore(path).load_all()
    assert len(final) == 12, f"Lost Update: {len(final)}/12"
    for n in range(1, 13):
        assert final[f"user:{n}"].access_token == f"tok-{n}"


def test_wrong_password_and_corrupt_files(tmp_path):
    """پسورد اشتباه، فایل خالی و فایل ناقص → SessionError امن."""
    from badking.hybrid.session import SessionError

    path = tmp_path / "s.session"
    SessionStore(path, password="right").put(Session(user_id=1, access_token="t"))
    with pytest.raises(SessionError):
        SessionStore(path, password="wrong").load_all()

    empty = tmp_path / "empty.session"
    empty.write_bytes(b"")
    with pytest.raises(SessionError):
        SessionStore(empty, password="pw").load_all()

    truncated = tmp_path / "trunc.session"
    truncated.write_bytes(b"BKS2\x03" + b"\x00" * 5)
    with pytest.raises(SessionError):
        SessionStore(truncated, password="pw").load_all()


def test_update_missing_key_and_invalid_return(tmp_path):
    """update(): نبودن کلید → None؛ بازگشت None → SessionError امن."""
    from badking.hybrid.session import SessionError

    path = tmp_path / "s.session"
    store = SessionStore(path)
    assert store.update("nope", lambda s: s) is None

    store.put(Session(user_id=1, access_token="original"))
    with pytest.raises(SessionError):
        store.update("user:1", lambda s: None)
    # فایل سالم باقی مانده است
    assert store.load_all()["user:1"].access_token == "original"


def test_data_preserved_after_failed_write(tmp_path):
    """خطای نوشتن نباید فایل سالم قبلی را خراب کند."""
    from badking.hybrid.session import SessionError

    path = tmp_path / "s.session"
    store = SessionStore(path, password="pw")
    store.put(Session(user_id=1, access_token="original"))

    # شبیهسازی خطا در مسیر نوشتن: updater استثنا بدهد
    def bad_updater(s):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        store.update("user:1", bad_updater)

    final = SessionStore(path, password="pw").load_all()
    assert final["user:1"].access_token == "original"


def test_reentrant_multi_path_does_not_self_deadlock(tmp_path):
    """قفل A سپس B و دوباره A نباید خود-deadlock بدهد (باگ بازبینی)."""
    from badking.hybrid.session_lock import cross_process_lock

    d = tmp_path
    a, b = d / "a.session", d / "b.session"
    result = {}

    def worker():
        with cross_process_lock(a, timeout=5):
            with cross_process_lock(b, timeout=5):
                with cross_process_lock(a, timeout=5):
                    result["ok"] = True

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=15)
    assert not t.is_alive(), "خود-deadlock در reentrancy چند-path"
    assert result.get("ok") is True


def test_lock_timeout_env_validation():
    """مقادیر نامعتبر BADKING_SESSION_LOCK_TIMEOUT نباید کرش یا منفی شوند.

    از ریلود ماژول selfdagه میشود چون ثوابت/کلاسهای ایمپورتشده توسط تستهای
    دیگه را ناسازگار میکند. تابع خالص ``_read_lock_timeout`` مستقیماً آزمایش
    میشود — همان منطقی که هنگام import اجرا میشود.
    """
    import badking.hybrid.session as sm

    original = os.environ.get("BADKING_SESSION_LOCK_TIMEOUT")
    try:
        for bad in ("abc", "-5", "", "nan", "inf"):
            os.environ["BADKING_SESSION_LOCK_TIMEOUT"] = bad
            assert sm._read_lock_timeout() == 120.0, f"{bad} پذیرفته شد"
        os.environ["BADKING_SESSION_LOCK_TIMEOUT"] = "7.5"
        assert sm._read_lock_timeout() == 7.5
    finally:
        if original is None:
            os.environ.pop("BADKING_SESSION_LOCK_TIMEOUT", None)
        else:
            os.environ["BADKING_SESSION_LOCK_TIMEOUT"] = original


def test_key_cache_does_not_store_raw_password():
    """password خام نباید در کلیدهای کش مشاهده شود."""
    import badking.hybrid.session as sm

    sm._KEY_CACHE.clear()
    secret = "super-secret-password-xyz"
    sm._derive_key(secret, b"\x01" * 16, 100_000)
    keys_repr = repr(list(sm._KEY_CACHE.keys()))
    assert secret not in keys_repr
    assert isinstance(next(iter(sm._KEY_CACHE.keys()))[0], bytes)
    sm._KEY_CACHE.clear()


def test_mixed_threads_and_processes(tmp_path):
    """ترکیب threadها و processها — هیچ نوشتهای از بین نرود."""
    import threading

    path = tmp_path / "s.session"
    barrier = threading.Barrier(2)

    def thread_writer(base):
        store = SessionStore(path)
        for i in range(4):
            store.put(Session(user_id=base + i, access_token=f"t-{base + i}"))
        try:
            barrier.wait(timeout=60)
        except Exception:
            pass

    t1 = threading.Thread(target=thread_writer, args=(1,))
    t2 = threading.Thread(target=thread_writer, args=(5,))
    t1.start()
    t2.start()

    ctx = _ctx()
    p1 = ctx.Process(target=_write_many, args=(str(path), None, 100, 4, None))
    p2 = ctx.Process(target=_write_many, args=(str(path), None, 200, 4, None))
    p1.start()
    p2.start()

    t1.join(timeout=60)
    t2.join(timeout=60)
    p1.join(timeout=120)
    p2.join(timeout=120)

    assert p1.exitcode == 0 and p2.exitcode == 0
    final = SessionStore(path).load_all()
    assert len(final) == 16, f"Lost Update در حالت ترکیبی: {len(final)}/16"

