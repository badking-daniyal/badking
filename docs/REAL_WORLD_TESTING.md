# Real-World Testing — Self Client

**تاریخ:** 2026-11-20
**قاعده:** تستهای Mock از تستهای زنده جدااند. هیچ موفقیت زندهای بدون حساب مجاز ادعا نمیشود.

---

## ساختار تستها

| مسیر | نوع | وضعیت |
|---|---|---|
| `tests/test_hybrid.py` | unit (آفلاین) | ✅ اجرا |
| `tests/test_self_client_audit.py` | regression (آفلاین) | ✅ اجرا |
| `tests/integration/test_self_client_mock.py` | integration MOCK | ✅ ۱۴ پاس |
| `tests/integration/test_self_client_live.py` | integration LIVE | ⛔ ۴ SKIP (BLOCKED) |

---

## پوشش Integration Mock (۱۴ تست)

| حوزه | تست | نتیجه |
|---|---|---|
| Authentication | نرمالسازی شماره، خطای کنترلشده | ✅ |
| OTP | جریان درخواست کد (Mock transport) | ✅ |
| Session Persistence | ذخیره/بازیابی رمزنگاریشده | ✅ |
| Session Recovery | رمز اشتباه رد میشود | ✅ |
| Backup/Restore | export/import zip | ✅ |
| Send Message | payload با شماره فیلد تأییدشده | ✅ |
| Receive Message | `_parse_message` | ✅ |
| Message History | `get_messages` خالی | ✅ |
| Editing | `UpdateMessage` | ✅ |
| Deletion | `DeleteMessage` | ✅ |
| Media Upload | خطای صریح وقتی URL نباشد | ✅ |
| RPC Execution | registry | ✅ |
| Inline Callback | `make_inline_keyboard` | ✅ |
| Reconnection | connect/close با transport تقلبی | ✅ |

---

## تستهای زنده — BLOCKED

چهار تست زنده عمداً SKIP میشوند:

```
SKIPPED [1] test_real_otp_login — BLOCKED: no authorized test account
SKIPPED [1] test_real_send_receive — BLOCKED
SKIPPED [1] test_real_upload_download — BLOCKED
SKIPPED [1] test_real_reconnect — BLOCKED
```

برای اجرا نیاز است:
- شماره آزمایشی مجاز (`BADKING_LIVE_PHONE`)
- کد SMS (`BADKING_LIVE_CODE`)
- پذیرش ریسک مسدودی اکانت

**تا زمانی که کاربر این موارد را فراهم نکند، هیچ موفقیت زندهای ادعا نمیشود.**

---

## Migration Runtime Validation

پروژه واقعی aiobale (bot.py، ۱۲۴۱ خط) در محیط ایزوله:

| مرحله | نتیجه |
|---|---|
| استخراج کامل (balecore + utils + aiobale 0.3.9) | ✅ |
| Migration (۶ تغییر) | ✅ |
| Syntax | ✅ |
| Import با دکوراتورهای balethon خنثی | ✅ `IMPORT_OK` |
| Import بدون خنثی کردن دکوراتورها | ❌ `AttributeError: Bot.Message` |

**یافته:** دکوراتورهای balethon (`@bot.Message`, `@bot.CallbackQuery`)
خارج از محدوده Migration Center (aiobale→BADKING)اند و تبدیل نمیشوند.
این یک شکاف مستندشده است، نه باگ پنهان.

---

## نتیجه

لایه Mock کاملاً قابل اجرا و پوششدهنده تمام ۱۳ حوزه مورد درخواست است.
لایه زنده **BLOCKED** و صریحاً علامتگذاری شده است.
