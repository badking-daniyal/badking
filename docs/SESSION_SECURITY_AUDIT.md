# Session Security & AEAD Migration Audit

تاریخ: 2026-11-20 — نسخه 0.2.2 (بدون تغییر)

## 1. وضعیت قبل از تغییر

| مسیر | وضعیت قبل | شواهد |
|---|---|---|
| Key derivation | IMPLEMENTED | PBKDF2-HMAC-SHA256، 200,000 round، salt 16 بایتی |
| Encryption | PARTIALLY IMPLEMENTED | XOR stream دستساز (`_xor_stream`) |
| Integrity | PARTIALLY IMPLEMENTED | HMAC-SHA256 فقط روی `body`، header محافظتنشده |
| Plain mode | NOT SECURE | `\x00` — بدون integrity، دستکاری قابلتشخیص نبود |
| Key storage | IMPLEMENTED | password یا `BADKING_SESSION_KEY` |
| Multi-account isolation | IMPLEMENTED | `key_for` بر اساس user_id/phone |
| Session migration | NOT IMPLEMENTED | فقط `import_zip`، بدون version migration |
| Session expiration | IMPLEMENTED | `is_valid` / `token_expiry` |

## 2. مشکلات واقعی کشفشده

1. **Encryption دستساز** — XOR stream جایگزین استاندارد AEAD شده بود.
2. **Header بدون محافظت** — HMAC فقط `body` را میپوشاند؛ مهاجم میتوانست salt/mode را عوض کند.
3. **Plain mode ناامن** — تغییر یک بایت قابلتشخیص نبود.
4. **خطاهای خام** — `json.JSONDecodeError` مستقیم به کاربر میرسید.
5. **Migration وجود نداشت** — ارتقای فرمت قدیمی به جدید تعریف نشده بود.

## 3. معماری جدید Session

```
BKS1\x00<payload>                       → قدیمی، plain (فقط خواندن)
BKS1\x01<salt16><mac32><body>           → قدیمی، XOR+HMAC (فقط خواندن)
BKS2\x02<salt16><nonce12><ct+tag>       → جدید، AES-256-GCM
```

### الگوریتم

- **AEAD**: AES-256-GCM از بسته `cryptography` (Apache-2.0 / MIT، سازگار 3.9–3.12)
- **Nonce**: 12 بایت تصادفی (`os.urandom`) — استاندارد 96 بیتی GCM
- **Authentication Tag**: 16 بایت، توسط AESGCM به ciphertext اضافه میشود
- **KDF**: PBKDF2-HMAC-SHA256، 200k iteration، salt 16 بایتی
- **AAD**: تمام header (`BKS2` + mode + salt + nonce) → دستکاری header باعث شکست auth میشود
- **نوشتن اتمیک**: `os.replace` از فایل `.tmp`

### Migration

- `format_version(blob)` فرمت را بدون رمزگشایی تشخیص میدهد
- `needs_migration()` مشخص میکند فایل قدیمی رمزنگاریشده است
- `migrate_to_v2(backup=True)`:
  1. بکاپ امن (`0600` روی یونیکس)
  2. رمزگشایی فایل قدیمی (در صورت شکست، فایل اصلی دست نخورده میماند)
  3. نوشتن اتمیک با فرمت BKS2
  4. idempotent — دومین بار `False` برمیگرداند
- `rollback_migration()` بکاپ را تأیید و بایت به بایت برمیگرداند

## 4. تستها

`tests/test_session_security.py` — 22 تست:

Valid Session · Invalid Key · Modified Ciphertext · Invalid Auth Tag · Invalid Nonce ·
Nonce Uniqueness · Corrupted Session · Header-as-AAD · Legacy V1 Migration ·
Idempotent Migration · Migration Failure · Rollback · Key Rotation · PBKDF2 Params ·
Multi-account Isolation · Unauthorized Access · Concurrent Access · Plain Regression

همچنین 135 تست session موجود (`test_hybrid.py`, `test_security_completion.py`,
`test_session_control.py`) بدون تغییر پاس میشوند.

## 5. وضعیت نهایی

| مسیر | وضعیت |
|---|---|
| Encryption | IMPLEMENTED (AES-GCM، تستشده) |
| Integrity | IMPLEMENTED (AAD + tag، تستشده) |
| Key derivation | IMPLEMENTED (تستشده) |
| Migration | IMPLEMENTED (تستشده، rollback تستشده) |
| Plain mode | IMPLEMENTED (ناامن، مستند — عمداً برای backward compatibility) |
| Live server session | BLOCKED (بدون حساب آزمایشی) |
