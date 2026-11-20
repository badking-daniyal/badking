# BADKING — Security Completion Report

**تاریخ:** 2026-11-20
**نسخه:** 0.2.2 (تغییر نکرد)
**HEAD قبل:** `33432b9`
**هدف:** تکمیل واقعی JWT Verification و اتصال OTPGuard به AuthFlow، بدون Regression.

---

## ۱. وضعیت قبل (Audit)

| قابلیت | وضعیت قبل | شاهد |
|---|---|---|
| JWT implementation | **NOT IMPLEMENTED** | فقط `Session.token_expiry()` payload را بدون verify میخواند (`session.py:71`) |
| Authentication Flow | PARTIALLY | `AuthFlow.sign_in` فقط `validate_otp` (format) را چک میکرد |
| OTPGuard | IMPLEMENTED ولی **جدا** | ۸ تست unit، ولی در AuthFlow استفاده نمیشد |
| PermissionPolicy | IMPLEMENTED | deny by default، ۹ تست |
| SessionManager | IMPLEMENTED | PBKDF2 + HMAC (دستساز، نه AEAD) |
| مسیر مصرف توکن | ناامن | `client.py:237` → `Bearer token` بدون verify |
| تستهای امنیتی | ۵۱ | OTP/self-client/access-control |

---

## ۲. مشکلات واقعی پیداشده

1. **توکن هیچگاه verify نمیشد** — تنها `exp` از payload خوانده میشد (قابل جعل).
2. **OTPGuard یک کلاس مستقل بود** — `AuthFlow` از آن استفاده نمیکرد.
3. **مسیر مصرف توکن (`SelfBot.connect`) چک امنیتی نداشت.**
4. **هیچ وابستگی JWT در `pyproject.toml` نبود** — بنابراین ادعای verify نمیتوانست واقعی باشد.

---

## ۳. تغییرات

### JWT Verification (واقعی، با PyJWT)
- فایل جدید: `badking/hybrid/jwt_verify.py`
- وابستگی: `PyJWT>=2.8,<3` در extras `hybrid` و `all` (MIT license، Python 3.9–3.12)
- الگوریتمهای مجاز: صریح و محدود (پیشفرض `HS256`) — الگوریتم **از هدر توکن خوانده نمیشود** (جلوگیری از Algorithm Confusion)
- رد: الگوریتم `none`، الگوریتم ناشناخته، توکن malformed، امضای نامعتبر، `exp`، `nbf`، `iss`، `aud`، claim گمشده
- خطاها امن: پیام خطا شامل توکن یا claim حساس نمیشود
- رمزنگاری دستساز: **هیچ** — تمام کارها توسط PyJWT

### چرا opt-in؟
بله توکنها را با کلید سرور امضا میکند و کلید عمومی در اختیار ما نیست. بنابراین نمیتوان امضای توکن واقعی بله را تأیید کرد. verification فقط وقتی فعال است که کاربر صریحاً `jwt_verifier=` بدهد. بدون آن وضعیت صریحاً `NOT_VERIFIED` است — هیچ ادعای غیرواقعیای نمیشود.

### OTPGuard → AuthFlow (واقعی)
- `AuthFlow(otp_guard=...)` اضافه شد
- حالت **blind**: کد واقعی را سرور پیامک میکند و نزد ما نیست، بنابراین OTPGuard فقط:
  - شمارش تلاش (Brute Force)
  - TTL (Expiration)
  - چالش مصرفشده (Replay)
  - صحت نهایی کد توسط سرور — هیچ ادعای محلیای نمیشود
- `mark_used()` بعد از تأیید موفق سرور
- transaction تازه چالش مستقل میگیرد (Reset صحیح state)

### مسیر مصرف توکن
- `AuthFlow.sign_in` و `refresh` → `_verify_token()` واقعی
- `SelfBot.connect` → verify قبل از ساخت هدر `Bearer`
- `SelfBot._do_login` → verifier و guard به AuthFlow منتقل میشوند

---

## ۴. فایلهای تغییرکرده

| فایل | تغییر |
|---|---|
| `badking/hybrid/jwt_verify.py` | **جدید** — JWTVerifier امن |
| `badking/hybrid/auth.py` | otp_guard + jwt_verifier، `_enforce_otp`، `_verify_token` |
| `badking/hybrid/client.py` | پارامترها + verify در connect + انتقال به AuthFlow |
| `badking/hybrid/security.py` | `issue_blind` / `check_blind` / `mark_used` |
| `badking/hybrid/__init__.py` | exportهای امنیتی |
| `pyproject.toml` | PyJWT در extras hybrid/all |
| `tests/test_jwt_verification.py` | **جدید** — ۲۶ تست |
| `tests/test_otp_authflow_integration.py` | **جدید** — ۶ تست |
| `tests/test_security_completion.py` | **جدید** — ۱۰ تست |
| `docs/SECURITY_COMPLETION_REPORT.md` | **جدید** — همین گزارش |

---

## ۵. تستهای اضافهشده (۴۲)

- JWT: valid, invalid signature, expired, not-yet-valid, leeway, invalid algorithm, algorithm confusion, none config/token, unknown algorithm, malformed (۶ حالت), missing exp, wrong issuer/audience, custom required claim, no secret leakage
- Integration AuthFlow: sign-in verify/accept, legacy behavior
- OTP: brute force (پیش از سرور), replay, expiry, reset, invalid format, legacy behavior
- Session tampering, wrong password, no key
- Permission bypass (`call` + `raw_call`), dangerous RPC opt-in
- SelfBot.connect JWT wiring, legacy behavior, refresh verify

**هیچ تستی حذف یا تضعیف نشد.**

---

## ۶. تستهای اجراشده

```
pytest tests/ -q --ignore=tests/live_check.py --ignore=tests/live_e2e.py -m "not live"
→ 1225 passed, 5 deselected, exit 0
```

---

## ۷. وضعیت نهایی

| قابلیت | وضعیت |
|---|---|
| JWT verification | **IMPLEMENTED + TESTED** (opt-in) |
| JWT در مسیر مصرف | **IMPLEMENTED + TESTED** |
| OTPGuard در AuthFlow | **IMPLEMENTED + TESTED** (blind mode) |
| PermissionPolicy | IMPLEMENTED + TESTED (بدون تغییر) |
| Session tampering detection | IMPLEMENTED + TESTED |
| توکن بله واقعی | **NOT_VERIFIED** — کلید سرور در دسترس نیست (صادقانه) |

---

## ۸. مشکلات و ریسکهای باقیمانده

1. **امضای توکن واقعی بله تأییدنشده** — کلید عمومی سرور لازم است (BLOCKED).
2. **OTP صحت محلی ندارد** — سرور تعیین میکند (ذاتاً محدودیت پروتکل).
3. **Session encryption دستساز است** (PBKDF2 + XOR + HMAC، نه AEAD) — وضعیت PARTIALLY.
4. **تست زنده self-bot** — نیاز به اکانت آزمایشی (BLOCKED).
5. **توکنهای افشاشده rotate نشدهاند** — فقط مالک حساب (BLOCKED).

---

## ۹. قوانین رعایتشده

نسخه 0.2.2 بدون تغییر · PyPI منتشر نشد · Git history تغییر نکرد · توکن واقعی نمایش داده نشد · فایل حساس خوانده/چاپ نشد · هیچ تستی حذف نشد · هیچ قابلیت سالمی حذف نشد · API غیرواقعی ساخته نشد · تغییر مخرب انجام نشد.
