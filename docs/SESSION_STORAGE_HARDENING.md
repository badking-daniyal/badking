# Session Storage Hardening — BADKING

تاریخ: 2026-11-20 · نسخه: 0.2.2 (بدون تغییر) · مبنا: `971a882`

ادامه بازبینی مستقل: تنها باقیماندههای امنیتی و قابلیتاطمینان Session Storage
بررسی و اصلاح شد. تمام اعداد از `[benchmarks/bench_session.py]` و تستهای اجرایی
گرفته شدهاند.

---

## ۱. بررسی PBKDF2 و تصمیم

### Benchmark واقعی (پیش از تغییر)

محیط: Python 3.9.10 · Windows 10 · cryptography 49.0.0 · ۹ اجرا بعد از ۳ warm-up.

| Iteration | Median | Min | Max |
|---|---|---|---|
| 200,000 (قدیمی) | 145.9 ms | 134.7 | 161.6 |
| 310,000 | 227.3 ms | 210.1 | 247.4 |
| **600,000** | **445.0 ms** | 429.2 | 522.9 |
| 1,000,000 | 726.6 ms | 700.6 | 920.0 |

### یافتهها و تصمیم

- **Iteration در هدر ذخیره نمیشد** — تغییر مستقیم 200k→600k تمام فایلهای BKS2
  موجود را غیرقابلخواندن میکرد. بنابراین تغییر مستقیم **رد شد**.
- **راهحل**: فرمت ``BKS3`` با هدر ۳۷ بایتی شامل `rounds:4` (big-endian) بعد از
  magic+mode. تعداد rounds داخل AAD هم هست → دستکاری آن یا GCM tag را میشکند
  یا توسط `_derive_key` رد میشود (محدوده 100k–5M).
- فایلهای ``BKS2`` قدیمی (هدر ۳۳ بایتی، 200k) **همچنان قابل خواندن**اند و با
  `migrate_to_v2()` به BKS3 ارتقا مییابند (بکاپ + rollback بایت به بایت).
- 600k مطابق توصیه OWASP PBKDF2-HMAC-SHA256 است؛ 1M رد شد (هزینه ۵× بدون سود
  متناسب).

### تأثیر performance (پس از تغییر)

| عملیات | قبل (200k) | بعد (600k) |
|---|---|---|
| encrypt/decrypt | ~140 ms | ~430 ms |
| save_all / load_all | ~140 ms | ~430 ms |
| migration BKS1→BKS2 | ~423 ms | ~778 ms |

**تفسیر صادقانه**: ~3× کندتر. Session فقط هنگام startup و تغییرات نادر خوانده/
نوشته میشود، نه در مسیر پیامها — پس تأخیر محسوس در عملیات عادی وجود ندارد.
اما migration دستی Several hundred ms طول میکشد که مستند است.

---

## ۲. Atomic Writes و fsync

پیادهسازی قبلی فقط `write_bytes` + `os.replace` بود (بدون fsync، با نام موقت
ثابت و قابل برخورد). حالا `_atomic_write`:

1. فایل موقت **منحصربهفرد** (pid + thread id + تصادفی) با `O_EXCL`
2. مجوز **0600** از لحظه ایجاد
3. `flush()` + `fsync()` فایل
4. `os.replace()` اتمیک
5. `fsync` پوشه (جایی که سیستم پشتیبانی کند؛ روی Windows بیصرفه رد میشود)
6. پاکسازی موقت در هر شکست

فایل مقصد تا لحظه replace دست نخورده است. شکست fsync / replace / نوشتن، فایل
اصلی را حفظ میکند (تست شده).

---

## ۳. Race Conditions

قفل `threading.RLock` **per-path** (WeakValueDictionary، بدون نشت حافظه) از
همه عملیات حساس محافظت میکند: `save_all`, `load_all`, `migrate_to_v2`,
`rollback_migration`, `backup`, `get`, `put`, `delete`.

- قفل **reentrant** است → migration که داخلاً backup/load/save را صدا میزند
  دچار deadlock نمیشود.
- تستها: ۲۰ نویسنده همزمان → **هیچ lost update** (۲۰ اکانت باقی ماند)، ۸ migration
  همزمان، ۸ rollback همزمان.
- **محدودیت صادقانه**: قفل فقط داخل همان process کار میکند. دو process جداگانه
  نیازمند قفل فایل سیستمی (fcntl/msvcrt)اند که در این نسخه پیادهسازی نشده —
  **BLOCKED / NOT_IMPLEMENTED**. نام موقت منحصربهفرد تا حدی از برخورد جلوگیری
  میکند ولی تضمین کامل نمیدهد.

---

## ۴. تستهای جدید (۱۷ مورد)

`tests/test_session_storage_hardening.py`:

- PBKDF2 v3 rounds و هدر، خواندن BKS2 قدیمی، migration v2→v3، rounds دستکاریشده،
  rounds نامعقول
- fsync فراخوانی میشود، شکست fsync فایل اصلی را حفظ میکند
- crash پیش از replace، crash پس از replace (فایل معتبر میماند)
- پاکسازی فایل موقت در شکست، فایل موقت خراب بیاثر است
- خطای permission فایل اصلی را حفظ میکند، session ناقص رد میشود
- save/migrate/rollback همزمان (چند thread)، قفل reentrant بدون deadlock

هیچ تستی حذف یا ضعیف نشد. ۴ assertion قدیمی `BKS2`→`BKS3` بهروز شدند (همان
قدرت، مقدار صحیح فرمت جدید).

---

## ۵. نتایج تست

| دسته | نتیجه |
|---|---|
| Unit + Security + Regression (آفلاین) | **۱۲۷۶ پاس، ۱ SKIP، ۶ deselected** |
| Session suites | ۸۴ پاس، ۱ SKIP |
| Integration (Mock) | ۱۴ پاس، ۵ live SKIP |
| امنیتی اجباری CI | ۵۱ پاس |
| Live (opt-in) | ۵ SKIP — **BLOCKED** (بدون حساب مجاز) |

---

## ۶. وضعیت CI

CI Run #37 (پس از بازبینی مستقل) سبز روی Python 3.9–3.12. تغییرات این مرحله
پس از push توسط CI مجدداً بررسی میشوند. محلی فقط Python 3.9 موجود است؛
سازگاری 3.10–3.12 توسط CI تأیید میگردد.

---

## ۷. ریسکهای باقیمانده

| ریسک | وضعیت |
|---|---|
| قفل بین processها | NOT_IMPLEMENTED (مستند شد) |
| fsync پوشه روی Windows | پشتیبانی نشد (بیصرفه رد میشود) |
| هزینه 600k (~430ms) | قابل قبول، مستند |
| تأیید پروتکل سرور بله (framing/correlation) | BLOCKED (غیرمرتبط با Storage) |
| Inline Callback / Media Download / Resume در SelfBot | NOT_IMPLEMENTED |

---

## ۸. ارزیابی نهایی Session Storage

**Session Storage از نظر امنیت رمزنگاری، نوشتن اتمیک، دوام در برابر شکست و
بازابی اطلاعات به سطح قابلقبول Production رسیده است** — با دو استثنای صادقانه:
قفل بین processها پیادهسازی نشده و تأیید پروتکل سرور (که مربوط به Self Client
است، نه Storage) هنوز BLOCKED است.

**اما کل BADKING still Production Ready نیست** تا زمانی که قابلیتهای Self Client
و تأیید پروتکل سرور تکمیل شوند. این سند تنها درباره Storage قضاوت میکند.
