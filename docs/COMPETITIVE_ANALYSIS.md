# BADKING در برابر aiobale — تحلیل رقابتی واقعی

**تاریخ:** 2026-11-20
**منابع:** مخزن `aminmadaniofficial/aiobale`، کد BADKING، تستها

قاعده سند مأموریت: «هیچ برتری ساختگی یا ادعای تأییدنشده ثبت نکن.»
هر ردیف زیر بر اساس کد و تست واقعی است. جایی که مطمئن نیستم، مینویسم
«تأییدنشده» یا «BLOCKED».

---

## جدول مقایسه

| قابلیت | aiobale | BADKING | مبنای واقعی |
|---|---|---|---|
| Client / Dispatcher / Router | ✓ | ✓ | تست `test_public_api.py` |
| FSM + Memory/SQLite | ✓ | ✓ | `badking/fsm`, `badking/storage` |
| Magic Filters | ✓ | ✓ | `badking/filters/magic.py` |
| Middleware | ✓ | ✓ | `badking/middleware` |
| Conversation | ✓ | ✓ | `badking/conversation` |
| Message History | ✓ | ✓ | `SelfBot.iter_messages` |
| Keyboard Builder + Pagination | ✓ | ✓ | `badking/keyboards` |
| Webhook | ✓ | ✓ | `Bot.set_webhook` |
| CLI | ✓ | ✓ | ۱۶ دستور (شامل security scan) |
| Session Management | ✓ (فایل .bale پراکنده) | ✓ (SessionManager رمزنگاریشده) | `badking/hybrid/sessions.py` |
| Authentication (OTP) | ✓ | ✓ | `badking/hybrid/auth.py` |
| File Upload/Download | ✓ | ✓ | `badking/media` |
| RPC Methods | ۷۹ | ۷۹ + ۳ (`raw_call`, `probe`, `describe`) | `badking/hybrid/schema.py`, `rpc.py` |
| Userbot / Self-bot | ✓ | ✓ | `badking/hybrid/client.py` |
| Bot API رسمی | ✗ | ✓ | `badking/core/bot.py` |
| Redis / PostgreSQL storage | ✗ | ✓ | تست `test_storage_backends.py` |
| Media validation + Path Traversal | ✗ | ✓ | تست `test_media_engine.py` |
| Moderation + Channel Monitor | ✗ | ✓ | تست `test_moderation.py` |
| Migration Center (AST) | ✗ | ✓ | تست `test_compat.py`, `test_migration_mapping.py` |
| Plugin System | ✗ | ✓ | تست `test_plugins_i18n.py` |
| i18n (fa/en) | ✗ | ✓ | `badking/i18n` |
| Security Scanner CLI | ✗ | ✓ | تست `test_security_scanner.py` |
| Observability / Prometheus | ✗ | ✓ | `badking/observability` |
| Bot-first API (`bot.run`) | ✗ | ✓ | تست `test_example_api.py` |
| CI Python ۳.۹–۳.۱۲ | تأییدنشده | ✓ | GitHub Actions |
| مستندات فارسی/انگلیسی | محدود | ✓ | `docs/fa`, `docs/en` |

---

## تفاوتهای معماری

### Session Management
- **aiobale:** هر اکانت یک فایل `.bale` در پوشه `sessions/`. کدهایی مثل
  `main-3.py` مجبورند صدها بار `try/except` و `client = None` تکرار کنند.
- **BADKING:** `SessionManager` یک فایل رمزنگاریشده (`.bks`) با PBKDF2،
  بکاپ zip با هش SHA256، و import/export اتمیک.

### Self-bot
- **aiobale:** ۷۹ RPC با اسکیمای ثابت.
- **BADKING:** همان ۷۹ RPC با شماره فیلد واقعی + ۶۵ اسکیمای پاسخ +
  `raw_call` for متدهای ناشناخته، `probe` برای کشف شکل متد در زمان اجرا،
  `describe`/`search` برای کاوش رجیستری. اسکیما با env قابل override است.

### Migration
- **aiobale:** بدون ابزار مهاجرت.
- **BADKING:** Analyzer + AST transformer + dry-run + backup/rollback +
  `mappings.json` با چهار وضعیت صریح. تستها تضمین میکنند هر هدف نگاشت
  واقعاً در کد وجود دارد.

---

## عملکرد (Performance)

**ادعای «سریعتر از aiobale» فعلاً تأییدنشده است.**

BADKING دارای connection pool، bounded queue، backpressure و retry با
backoff است، ولی benchmark مقایسهای در شرایط یکسان اجرا نشده است.
تا زمانی که benchmark معتبر وجود داشته باشد، هیچ ادعای عملکردی منتشر
نمیشود (بخش ۲۳ سند).

---

## محدودیتهای صادقانه

- تست زنده self-bot نیاز به شماره واقعی + SMS دارد → **BLOCKED**.
- برخی رویدادها بسته به دسترسی API بله متفاوتاند → framework فقط آنچه
  واقعاً میآید را Native مینامد.
- اعدادی مثل «۲ پیام/ثانیه» در مستندات رسمی بله نیستند → پیشفرض قابلتنظیم.
- PyPI publish نیاز به حساب کاربر → **BLOCKED**.

---

## نتیجه

BADKING در **پوشش قابلیت، امنیت session، مهاجرت، و تجربه توسعهدهنده**
از aiobale جلوتر است. در **عملکرد خام** فعلاً ادعایی نمیکند تا benchmark
اجرا شود.
