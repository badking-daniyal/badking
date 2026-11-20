# Security Review — Session, Token, OTP, RPC

**تاریخ:** 2026-11-20
**دامنه:** `badking/hybrid/`, `badking/security/`, `.gitignore`, Git history

---

## ۱. Session Encryption

| بررسی | نتیجه |
|---|---|
| الگوریتم | PBKDF2-HMAC-SHA256، ۲۰۰k iteration، salt ۱۶ بایت |
| integrity | HMAC-SHA256 با `compare_digest` |
| نوشتن فایل | atomic (`os.replace`) |
| پیشفرض | **بدون رمز = متن آشکار** (`mode=0x00`) |
| ضعف | رمزنگاری دستساز (XOR stream)، نه AEAD؛ MAC فقط body را میپوشاند |
| توصیه | رمز قوی بده: `BADKING_SESSION_KEY` |

**وضعیت:** PARTIALLY_SECURE — قابل قبول برای obfuscation، نه برای data حساس.high-value.

---

## ۲. Token Handling

| بررسی | نتیجه |
|---|---|
| لاگ توکن | ❌ فقط `user_id` لاگ میشود — توKEN لاگ نمیشود |
| `Secrets.mask()` | ✅ وجود دارد |
| پاکسازی در لاگ | ✅ `logging_mw` و `redact` |
| JWT expiry | ✅ خوانده میشود ولی امضا verify نمیشود |
| refresh | ❌ `AuthFlow.refresh` کد مرده است — منقضی شدن ⇒ SMS دوباره |

**وضعیت:** PARTIALLY_IMPLEMENTED

---

## ۳. OTP

| بررسی | نتیجه |
|---|---|
| ذخیره transaction_hash | در حافظه `_pending`، بدون TTL |
| لاگ شماره تلفن | ⚠️ `auth.py` و `sessions.py` شماره کامل را لاگ میکنند (PII) |
| اعتبارسنجی کد | فقط stripping فاصله/خط تیره، بدون بررسی طول |
| 2FA | heuristic (`"password" in error` یا code 400/401) — میتواند اشتباه بگیرد |

**وضعیت:** PARTIALLY_IMPLEMENTED — نیاز به بهبود قبل از production.

---

## ۴. مجوزهای RPC

| بررسی | نتیجه |
|---|---|
| رجیستری ۷۹ متد | ✅ |
| پرچم `dangerous` | ✅ در `RpcSpec` وجود دارد ولی **اجرا نمیشود** |
| RBAC در self-bot | ❌ ندارد |
| `raw_call` | ✅ هر فیلدی را میپذیرد — بدون محدودیت |

**وضعیت:** NOT_IMPLEMENTED — pragma امنیتی `dangerous` فقط مستند است، نه اعمالشده.

---

## ۵. اطلاعات حساس در مخزن

| بررسی | نتیجه |
|---|---|
| `.env` در git | ✅ track نمیشود، gitignore میپوشاند |
| توKEN واقعی در `.env` محلی | ⚠️ وجود دارد (کاربر، خارج از git) |
| توKEN واقعی در `backup.zip` (D:\AI) | ⚠️ وجود دارد — **داده کاربر، حذف نشد** |
| Secret Detection | ✅ `badking security scan` — ۰ CRITICAL/HIGH در کد |

**هشدار:** `backup.zip` حاوی `BALE_BOT_TOKEN` واقعی و `ADMIN1_ID/2_ID` است.
پیشنهاد: آنرا به محیط امن منتقل یا توKEN را rotate کن.

---

## ۶. یافتههای Scanner (کد)

```
MEDIUM: 5  — silent exception (compat, connectors, transport)
LOW:    6  — assert در کد production
CRITICAL: 0
HIGH:     0
```

هیچ توKEN، کلید خصوصی، eval/exec یا SSL disabled در کد BADKING پیدا نشد.

---

## ۷. نتیجه

| حوزه | وضعیت |
|---|---|
| Session encryption | PARTIALLY_IMPLEMENTED |
| Token handling | PARTIALLY_IMPLEMENTED |
| OTP | PARTIALLY_IMPLEMENTED |
| RPC permissions | NOT_IMPLEMENTED |
| Secret hygiene در مخزن | IMPLEMENTED |
| Security scanner | IMPLEMENTED |

**برای production:** حداقل سه مورد OTP/token/RBAC باید بهبود یابند.
