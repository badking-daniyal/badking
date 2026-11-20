# Security Hardening — ممیزی و تقویت امنیت

**تاریخ:** 2026-11-20
**قاعده:** هیچ Secret واقعی در این سند چاپ نشده است. فقط الگو، مسیر و fingerprint (هش کوتاه) ذکر میشود.

---

## ۱. Critical Secret Audit

### الف) فایلهای Backup

اسکن `backup.zip` (تمام فایلها، الگوهای token/private key/phone):

| الگو | تعداد فایل | محل |
|---|---:|---|
| `BALE_BOT_TOKEN` | ۳ | `backup/.env`، `backup/.env.backup-before-token-fix`، `backup/.env.backup-admin-fix` |
| کلید خصوصی | ۰ | — |
| شماره تلفن (PII) | ۰ در فایلهای پروژه* | فقط در کتابخانههای pip (داده تست) |

* دو fingerprint متفاوت شناسایی شد ⇒ **دو توKEN جداگانه** در بکاپ وجود دارد.
هش کوتاه: `2c51f4d49901` و `f9e66ae23637` (مقادیر اصلی چاپ نشدند).

### ب) Git History

| بررسی | نتیجه |
|---|---|
| تعداد commit | ۲۹ |
| تعداد object | ۶۲۴ |
| blob حاوی الگوی توKEN | ۱ |
| آن blob | `tests/test_security_scanner.py` — fixture جعلی `PRIVATE KEY ... abc` |
| تطابق با توKEN بکاپ | ❌ هیچکدام (fingerprint متفاوت) |
| **نتیجه** | ✅ **git history پاک است** |

### ج) اقدامات انجامشده

1. `.gitignore` تقویت شد: `*.zip`, `*.bak`, `*.bks`, `*.session`, `*.pem`, `*.key`, `backup*/`
2. توKEN نمونه مستندات (`123456789:AA...`) در `START_HERE.md` به `YOUR_BOT_TOKEN_HERE` تغییر یافت تا Scanner هشدار ندهد
3. تست قابل تکرار `tests/test_secret_audit.py` اضافه شد (۷ تست)
4. **backup.zip اصلی حذف یا تغییر نکرد** — طبق دستور صریح تو

### د) توKEN افشاشده — مراحل ابطال (باید توسط تو انجام شود)

من نمیتوانم توKEN بله را ابطال کنم (نیاز به حساب تو). مراحل:

1. وارد پنل توسعهدهندگان بله شو و ربات مربوط به توKEN `2c51...` و `f9e6...` را پیدا کن
2. **Revoking token** / «بازنشانی توکن» را بزن — توKEN قدیمی بلافاصله باطل میشود
3. توKEN جدید بگیر و فقط در `.env` محلی (که track نمیشود) بگذار
4. اگر ربات در سرور دیگری هم مستقر است، آنجا را هم آپدیت کن
5. بکاپ قدیمی (`backup.zip`) را به محیط امن منتقل کن یا پس از اطمینان از rotate، حذفش کن (با تأیید تو)

⚠️ **تا زمانی که rotate انجام نشود، توKENهای بکاپ معتبر فرض میشوند.**

---

## ۲. Self Client Security — وضعیت واقعی

| قابلیت | وضعیت | تست |
|---|---|---|
| RBAC (deny by default) | IMPLEMENTED | `test_self_client_security.py` (۱۰ تست) |
| OTP validation (۴-۸ رقم) | IMPLEMENTED | ۱۳ تست |
| Secure logging ( masking ) | IMPLEMENTED | ۵ تست |
| Session expiration | IMPLEMENTED | ۵ تست |
| Constant-time compare | IMPLEMENTED | ۱ تست |
| Auth error hints | IMPLEMENTED | ۱ تست |
| Session encryption (PBKDF2 + HMAC) | PARTIALLY_IMPLEMENTED | تستهای موجود در `test_session_control.py` |
| JWT signature verification | NOT_IMPLEMENTED | — |
| Self-bot permission enforcement در تمام مسیرها | PARTIALLY_IMPLEMENTED | فقط `call`/`raw_call` پوشش دارد |

### جزئیات RBAC

- `PermissionPolicy` با `deny by default`
- RPCهای خطرناک (`DeleteMessage`, `KickUser`, `SignOut`, ...) فقط با `allow_dangerous=True`
- **سازگاری:** پیشفرض `SelfBot(permissions=None)` = بدون محدودیت (رفتار نسخه قبل).
  برای امنیت باید صریحاً policy بدهی. این محدودیت صادقانه مستند است.

### جزئیات لاگ

- `auth.py` حالا شماره را با `mask_phone()` چاپ میکند (فقط ۴ رقم آخر)
- تست `test_auth_logger_does_not_log_full_phone` تضمین میکند شماره کامل وارد لاگ نشود

---

## ۳..Scanner

`badking security scan` روی کل مخزن: **۰ CRITICAL، ۰ HIGH**.
یافتههای باقیمانده: ۵ MEDIUM (silent exception) + ۶ LOW (assert) — پیش از این مستند شدهاند.

---

## ۴. نتیجه

| مورد | وضعیت |
|---|---|
| Git history پاک | ✅ IMPLEMENTED |
| محافظت .gitignore | ✅ IMPLEMENTED |
| Secret scanner قابل تکرار | ✅ IMPLEMENTED |
| افشای توKEN بکاپ | ⚠️ BLOCKED — نیاز به rotate توسط کاربر |
| Self-bot RBAC | ✅ IMPLEMENTED (با پیشفرض سازگاری) |
| JWT verify | ❌ NOT_IMPLEMENTED |
