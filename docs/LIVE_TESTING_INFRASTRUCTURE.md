# Live Testing Infrastructure — Self Client

تاریخ: 2026-11-20 — نسخه 0.2.2

## وضعیت

زیرساخت live testing **طراحی و پیادهسازی شد** ولی **BLOCKED** است: هیچ حساب
آزمایشی مجازی در اختیار نیست. هیچ موفقیت زندهای ادعا نمیشود.

## طراحی

فایل: `tests/integration/test_self_client_live.py`

| اصل | پیادهسازی |
|---|---|
| حساب آزمایشی مجزا | متغیرهای `BADKING_LIVE_PHONE` / `BADKING_LIVE_CODE` |
| عدم نمایش اطلاعات حساس | تابع `_mask()` — شماره و توکن ماسک میشوند |
| بدون عملیات مخرب | فقط `get_me`, `iter_dialogs`, `iter_messages`, reconnect |
| opt-in | marker `live` + `skipif` وقتی credential نباشد |
| جداسازی Mock / Live | `tests/integration/test_self_client_mock.py` (14 پاس) در برابر live (5 SKIP) |

## تستهای live (همه SKIP بدون credential)

1. `test_real_login_returns_identity` — ورود واقعی و دریافت id
2. `test_session_is_persisted` — توکن پس از connect وجود دارد (چاپ نمیشود)
3. `test_read_dialogs` — خواندن ۵ گفتگو بدون ارسال
4. `test_read_history_of_self_chat` — خواندن ۳ پیام بدون تغییر
5. `test_reconnect_preserves_session` — بستن/بازکردن اتصال بدون از دست دادن session

## نتیجه اجرا

```
14 passed, 5 skipped
SKIPPED [5] BLOCKED: no authorized test account
```

## پیش نیاز برای رفع BLOCK

ارائه یک حساب بله آزمایشی مجاز توسط صاحب پروژه. تا آن زمان تمام تستهای
زنده SKIP باقی میمانند و نباید به عنوان PASS شمارش شوند.
