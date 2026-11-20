# BADKING — کمبودهای باقیمانده

**تاریخ:** 2026-11-20
**وضعیت:** پس از سه اولویت (Self Client audit، Migration validation، ۳۹ صفحه مستندات)

این فایل صادقانه میگوید چه چیزی **کامل نشده** است. هیچ موردی پنهان نمیشود.

---

## BLOCKED — بدون حساب/مجوز خارجی قابل حل نیست

| مورد | دلیل | اقدام لازم |
|---|---|---|
| تست زنده self-bot | نیاز به شماره واقعی + SMS + ریسک مسدودی | کاربر یک اکانت آزمایشی فراهم کند |
| تأیید شماره فیلدهای RPC | نیاز به ترافیک واقعی بله / سورس aiobale | Capture کردن ترافیک یا `.proto` |
| تأیید endpointهای auth | نیاز به سرور واقعی | همان above |
| تأیید framing و `req_id` | حدس است (`transport.py`) | ترافیک واقعی |
| انتشار PyPI | نیاز به حساب و توکن کاربر | کاربر اقدام کند |
| اجرای ربات مهاجرت یافته | نیاز به توکن، aiobale، دیتابیس | محیط آزمایشی |

---

## NOT_IMPLEMENTED — قابل پیادهسازی ولی انجام نشد

| مورد | بخش سند | توضیح |
|---|---|---|
| `SelfBot.download_file` | ۶، ۱۴ | `files.GetNasimFileUrl` در رجیستری هست ولی متد کلاینت نیست |
| Media resume | ۱۴ | interrupted transfer از سرور گرفته نمیشود |
| Inline callback در self-bot | ۶ | فقط در لایه ربات رسمی هست؛ `@bot.on` update parser عملاً Message نمیدهد |
| MySQL / MongoDB storage | ۱۰ | اختیاری است؛ فعلاً ۴ بکاند |
| `badking generate ...` CLI | ۱۷ | scaffolding پایه هست، الگوهای ecommerce/ai/admin/channel نیستند |
| `badking debug` / `profile` | ۱۷ | دستورهای پیشنهادی سند |
| OpenTelemetry tracing | ۲۱ | metrics و Prometheus exporter هست، tracing نه |
| Benchmark مقایسهای | ۲۳ | فقط BADKING اندازهگیری شد، نه aiobale |
| Memory/CPU در benchmark | ۲۳ | فقط latency و RPS |

---

## PARTIALLY_IMPLEMENTED — هست ولی ناقص

| مورد | وضعیت | نقص |
|---|---|---|
| Session encryption | PBKDF2 + XOR + HMAC | دستساز، نه AEAD؛ MAC فقط body را میپوشاند |
| Self-bot error handling | transport errors | دو سلسلهمراتب جدا؛ `RpcFailed` و `RateState.learn` کد مردهاند |
| Self-bot auth field table | `auth.py` جدول جدا | با `schema.py` ناسازگار (`code=3` در برابر `code=2`) — کدام درست است BLOCKED |
| `probe` | رجیستری محلی | سرور واقعی را پروب نمیکند — صریحاً `server_verified=False` |
| `iter_messages(reverse=True)` | معکوس داخل صفحه | ترتیب کل صفحات معکوس نمیشود |
| `iter_dialogs` | pagination | cursor تاریخ را با تعداد ردیف زیاد میکند |

---

## ریسکهای شناختهشده (تأییدشده توسط ممیزی)

- **ادعای «۷۹ RPC استخراجشده از aiobale» فقط متنی است.** نه سورس aiobale در workspace هست، نه `.proto`، نه generator، نه citation در `schema.py`.
- **self-bot میتواند اکانت را مسدود کند.** پیشفرض خاموش است.
- **`websockets` pins به `<14.0`** — در نسخه 14+ `extra_headers` تغییر میکند.
- **هیچ تستی حذف نشد.** تمام ۱۰۴۱ تست از اجرای واقعی میآیند.

---

## اولویت پیشنهادی بعدی (پس از تأیید کاربر)

1. فراهم کردن اکانت آزمایشی → تست زنده self-bot و تکمیل `SELF_CLIENT_AUDIT.md`
2. Capture ترافیک → اصلاح شماره فیلدها
3. `SelfBot.download_file` + media resume
4. CLI `generate`/`debug`/`profile`
5. Benchmark مقایسهای و memory/CPU
6. PyPI publish (پس از تأیید صریح)

---

**قاعده:** تا زمانی که یک مورد BLOCKED است، نباید بهعنوان «تکمیلشده» معرفی شود.
