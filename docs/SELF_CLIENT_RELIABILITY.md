# Self Client Reliability Audit — FINAL

**تاریخ:** 2026-11-20
**قاعده:** هر مورد دقیقاً یکی از وضعیتها را دارد. Mock از Live جدا است.

---

## جدول وضعیت

| مورد | وضعیت | شاهد |
|---|---|---|
| Connection lifecycle | IMPLEMENTED | `transport.py::connect/close`، تست shutdown |
| Timeout handling | IMPLEMENTED | `request()` → `RpcTimeout`، ۲ تست |
| Retry policy | IMPLEMENTED | `resilience.py::RetryPolicy`، ۴ تست |
| Flood wait | IMPLEMENTED | `RateState` + `retry_after` در `RpcFailed` |
| RPC error mapping | IMPLEMENTED | `reliability.py`، ۶ تست |
| Correlation ID | IMPLEMENTED | `_stamp_req_id`/`_peek_req_id` + Future dict |
| Request ID (`req_id`) | PARTIALLY_IMPLEMENTED | فیلد 1 varint (قرارداد حدسی، روی wire تأیید نشده) |
| Binary framing | IMPLEMENTED | `length` + `raw`، ۵ تست |
| Graceful shutdown | IMPLEMENTED | `close()` idempotent، ۱ تست |
| Session expiration | PARTIALLY_IMPLEMENTED | `Session.is_valid()` چک `exp` میکند ولی **امضا verify نمیشود**؛ `SessionExpiry` جداگانه تست شده ولی به client متصل نیست |
| Session recovery | PARTIALLY_IMPLEMENTED | save/load/encrypt تست شده (Mock)؛ recovery از سرور BLOCKED |
| Secure logging | IMPLEMENTED | `mask_phone/token/hash` + تست لاگ |
| OTP attempt/expiry/reuse | IMPLEMENTED | `OTPGuard` + ۸ تست (اما به `AuthFlow` متصل نیست → PARTIALLY در عمل) |
| JWT signature verification | NOT_IMPLEMENTED | فقط payload decode بدون verify |
| Message dedup | NOT_IMPLEMENTED | — |
| Live wire framing / req_id | BLOCKED | نیاز به حساب واقعی |

---

## جزئیات مهم

### Session Expiration — PARTIALLY_IMPLEMENTED

```python
Session.is_valid()       # ✅ exp را از payload میخواند
Session.token_expiry()   # ⚠️ بدون verify امضا ("بدون verify امضا" صریحاً در docstring)
SessionExpiry            # ✅ کلاس جداگانه + ۵ تست، ولی client از آن استفاده نمیکند
```

### OTP — IMPLEMENTED (ماژول) / PARTIALLY (اتصال)

`OTPGuard` محدودیت تلاش، انقضا و جلوگیری از replay دارد (۸ تست) ولی `AuthFlow`
هنوز از آن استفاده نمیکند — `AuthFlow.sign_in` فقط `validate_otp` (format) را صدا میزند.

### req_id — PARTIALLY_IMPLEMENTED

`REQ_ID_FIELD = 1` یک **قرارداد حدسی** است (در `PROTOCOL_VERIFICATION.md` مستند).
تا زمانی که ترافیک واقعی capture نشود، نمیتوان ادعا کرد سرور دقیقاً از فیلد 1 استفاده میکند.

---

## تستها: Mock در برابر Live

| دسته | فایل | تعداد | وضعیت |
|---|---|---:|---|
| Mock integration | `tests/integration/test_self_client_mock.py` | ۱۳ | ✅ اجرا میشود |
| Live integration | `tests/integration/test_self_client_live.py` | ۵ | ⛔ SKIP/BLOCKED بدون حساب آزمایشی |
| Reliability unit | `tests/test_self_client_reliability.py` | ۱۷ | ✅ |
| Security unit | `tests/test_self_client_security.py` + `test_otp_security.py` | ~۴۰ | ✅ |

**هیچ تست Mockی به عنوان Live معرفی نشده است.**

---

## BLOCKED — نیاز به حساب واقعی

| مورد | دلیل |
|---|---|
| صحت `req_id` روی wire | capture ترافیک لازم است |
| Connection recovery در قطع واقعی | اتصال زنده لازم است |
| Flood wait واقعی سرور | حساب آزمایشی لازم است |
| Server-side session restore | حساب آزمایشی لازم است |
| OTP زنده (SMS) | شماره + SMS لازم است |

---

## وضعیت کلی

| مورد | وضعیت |
|---|---|
| Reliability core (framing/timeout/retry/error/shutdown) | ✅ IMPLEMENTED + TESTED |
| Session/OTP تکمیل اتصال | ⚠️ PARTIALLY_IMPLEMENTED |
| JWT verify | ❌ NOT_IMPLEMENTED |
| Live verification | ⛔ BLOCKED |
