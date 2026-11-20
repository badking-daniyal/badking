# Independent Security & Engineering Review — BADKING

تاریخ: 2026-11-20 · نسخه: 0.2.2 (بدون تغییر) · مبنا: `7f5bddc`

این بازبینی مستقل است: به گزارشهای قبلی اعتماد نشد. تمام موارد از روی کد منبع
خوانده و با اسکریپت reproduction اجرایی تأیید شدند.

---

## ۱. خلاصه مدیریتی

هسته رمزنگاری BKS2 (AES-GCM) **صحیح** است: nonce تصادفی، AAD درست، تأیید tag،
و PBKDF2 استاندارد — هیچ نقص AAD، nonce reuse یا tag-bypass یافت نشد.

اما ممیزی مستقل **۷ مشکل واقعی** کشف کرد که ۶ تای آنها عملاً قابل بازتولید
بودند. تمام آنها اصلاح و با تست regression پوشش داده شدند.

**ارزیابی Production: آماده نیست.** دلیل اصلی: تأیید پروتکل سرور بله (framing،
correlation، offset_date) **BLOCKED** است و قابلیتهای Inline Callback / Media
Download / Media Resume در Self Client وجود ندارند.

---

## ۲. وضعیت رمزنگاری (بررسی و تأییدشده)

| مورد | وضعیت | شواهد |
|---|---|---|
| Nonce ۱۲ بایتی تصادفی | SECURE | `session.py:187` `os.urandom(12)`، هر save مجدداً تولید میشود |
| تأیید Authentication Tag | SECURE | `AESGCM.decrypt` + `InvalidTag` → `SessionError` عمومی |
| AAD = header کامل (۳۳ بایت) | SECURE | encrypt `blob[:33]` = decrypt `blob[:33]`، انطباق دقیق |
| Salt ۱۶ بایتی تصادفی | SECURE | `os.urandom(16)`، در header ذخیره میشود |
| PBKDF2-HMAC-SHA256 200k | SECURE (پیادهسازی) / WEAK (سختی) | کمتر از توصیه ۶۰۰k OWASP |
| چرخش کلید | SECURE | `save_all` هر بار با رمز فعلی مجدداً مشتق میکند |
| خطاهای امن | SECURE | پیامهای عمومی، `from None`، بدون نشت محتوا |

---

## ۳. آسیبپذیریهای قطعی (همه اصلاح شدند)

| # | مشکل | فایل / تابع | بازتولید | اصلاح |
|---|---|---|---|---|
| F1 | rollback بکاپ خراب را میپذیرفت و فایل سالم را با داده غیرقابلخواندن جایگزین میکرد (فقط ۶ بایت magic چک میشد) | `session.py::rollback_migration` | بایت ۶۰ بکاپ را عوض کن، rollback → فایل زنده ناخوانده میشود | بکاپ کاملاً رمزگشایی و validate میشود |
| F2 | `AttributeError` خام از `Session.from_dict` | `session.py::from_dict` | `sessions={"x":123}` → raw exception | تبدیل به `SessionError` امن |
| F3 | نشت توکنها در `repr(Session)` | `session.py::Session` | `repr(session)` شامل access_token بود | `repr=False` برای فیلدهای حساس |
| F4 | تزریق session plaintext بدون رمز، با دسترسی نوشتن | `session.py::_decrypt` | فایل `BKS1\x00` با توکن جعلی → بدون رمز پذیرفته میشد | خواندن plain وقتی password هست، فقط با `allow_plain` صریح (migration) |
| F5 | FIFO پاسخ دیرهنگام را به درخواست اشتباه نسبت میداد | `transport.py::_dispatch` | timeout سپس پاسخ دیر → به درخواست بعدی تخصیص مییافت | پیشفرض `strict`: پاسخ بدون req_id به update میرود |
| F6 | FIFO آپدیت ناخواسته را بعنوان پاسخ میگرفت | `transport.py::_dispatch` | `_dispatch(unsolicited)` → future پر میشد | حالت strict آپدیت را به on_update میدهد |
| F7 | فایل session با مجوز پیشفرض (0644 یونیکس) ساخته میشد | `session.py::save_all` | بررسی کد: برخلاف backup، chmod نبود | نوشتن با `0600` + chmod |

همچنین `test_transport_payload_untouched_by_default` قبلاً tautology بود
(یک bytes literal را با خودش مقایسه میکرد) — به تست واقعی تبدیل شد.

---

## ۴. ریسکهای احتمالی (نیازمند شواهد بیشتر)

| ریسک | وضعیت | دلیل |
|---|---|---|
| PBKDF2 200k در برابر حمله آفلاین | WEAK | رمز تنها secret است؛ 600k توصیه فعلی است |
| همزمانی MULTI-PROCESS migration | NOT_VERIFIED | نام فایل موقت ثابت + بدون قفل؛ تست تک-process آنرا پوشش نمیدهد |
| قطع برق هنگام نوشتن (fsync) | NOT_VERIFIED | `os.replace` اتمیک است ولی fsync وجود ندارد |
| BKS1 قدیمی (XOR+HMAC) | WEAK | HMAC فقط body را میپوشاند؛ `compare_digest` درست است |
| downgrade به BKS1-plain توسط مهاجم | PARTIALLY_MITIGATED | با password تنظیمشده رد میشود؛ بدون password ذاتاً ناامن است |

---

## ۵. وضعیت Migration

- مسیر عادی migration امن است: backup قبل از تغییر، رمزگشایی قبل از نوشتن، `os.replace` اتمیک.
- **idempotent** و **rollback بایت به بایت** تست شدهاند.
- ۱۰ سناریوی شکست بررسی شد: ۸ SAFE، ۱ UNSAFE (F1، اصلاح شد)، ۱ NOT_VERIFIED (fsync).
- شکست migration در مسیر عادی هیچگاه فایل اصلی را از بین نمیبرد.

---

## ۶. وضعیت Request Correlation

- **FIFO ذاتاً ناامن است**: سرور بله تضمین نکرده پاسخها به ترتیب ارسال برسند.
- پیشفرض حالا `strict` است: پاسخی که req_id قابل تشخیص ندارد، بعنوان update تحویل
  میشود و درخواست timeout میخورد. انتساب اشتباه رخ نمیدهد.
- حالت `fifo` فقط صریح و با هشدار موجود است.
- **correlation واقعی سرور BLOCKED** — بدون ترافیک واقعی نمیتوان فیلد req_id را حدس زد.

---

## ۷. وضعیت Client API (سطح اعتبارسنجی)

| قابلیت | سطح |
|---|---|
| RPC Framing (codec) | IMPLEMENTED_AND_UNIT_TESTED |
| Correlation (FIFO path) | IMPLEMENTED_AND_UNIT_TESTED (ولی ناامن — strict پیشفرض شد) |
| `iter_dialogs` pagination | IMPLEMENTED_AND_UNIT_TESTED (فقط با FakeTransport) |
| معنای واقعی `offset_date` | SOURCE_INFERRED / BLOCKED |
| Inline Callback | NOT_IMPORTED → **NOT_IMPLEMENTED** |
| Media Download (SelfBot) | **NOT_IMPLEMENTED** |
| Media Resume | **NOT_IMPLEMENTED** |

**LIVE_VERIFIED: هیچ موردی.** تطابق با سورس aiobale 0.3.9 (فقط method definitions،
بدون transport/framing) تأیید پروتکل سرور نیست. تست `result is not None` برای
inline keyboard تأیید رفتاری نیست.

---

## ۸. نتایج تستها

| دسته | نتیجه |
|---|---|
| Unit + Security + Regression (آفلاین) | **1259 passed, 1 skipped, 6 deselected** |
| Integration (Mock) | 14 passed, 5 live skipped |
| تستهای امنیتی اجباری CI | 51 passed |
| Live (opt-in) | 5 SKIP — **BLOCKED** (بدون حساب مجاز) |
| Regression اسکریپت reproduction | تمام یافتهها رفع شدند |

---

## ۹. وضعیت CI

- Run #36 (پس از رفع نصب `cryptography`) **سبز** روی Python 3.9 / 3.10 / 3.11 / 3.12.
- محلی فقط Python 3.9 موجود است؛ ۳٫۱۰–۳٫۱۲ توسط CI تأیید شدند.

---

## ۱۰. برنامه اصلاحات

### CRITICAL
هیچ مورد باقیماندهای که عملاً قابل بازتولید باشد و اصلاح نشده باشد.

### HIGH (BLOCKED — نیازمند شواهد سرور)
- تأیید correlation واقعی (req_id) — `transport.py` · بدون ترافیک سرور قابل حل نیست.
- تأیید framing واقعی — `transport.py:9-11` · پیشفرض length-prefixed حدس است.

### MEDIUM
- PBKDF2 200k → 600k (`session.py:49`) — نیازمند تصمیم سازگاری با sessionهای موجود.
- قفل فایل / نام موقت منحصربهفرد برای migration همزمان (`session.py:255,279`).
- fsync قبل از `os.replace` برای دوام در برابر قطع برق.

### LOW
- هشدار deprecation هنگام خواندن BKS1 (`session.py:203`).
- اضافه کردن `answer_callback` و `download_file` به SelfBot (قابلیت جدید، خارج از این مأموریت).

---

## ۱۱. موانع Production Ready

1. **عدم تأیید پروتکل سرور** — مهمترین مانع. تمام ارتباط self-bot بر حدسهای
   محلی (framing، correlation، offset_date) استوار است.
2. **عدم وجود قابلیتهای اساسی Self Client** — Inline Callback، Media Download،
   Media Resume پیادهسازی نشدهاند.
3. **Live Testing BLOCKED** — بدون حساب آزمایشی مجاز، هیچ ادعای موفقیت زندهای
   نمیتوان کرد.
4. **سختی KDF و همزمانی** — موارد MEDIUM بالا.

**ارزیابی نهایی:** BADKING از نظر ساختار کد، تست و امنیت session پیشرفت واقعی
داشته و ۶ نقص اثباتشده آن اصلاح شد. ولی **نمیتوان آنراProduction Ready اعلام
کرد** تا زمانی که پروتکل سرور تأیید و قابلیتهای یادشده پیادهسازی شوند.
