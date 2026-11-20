# BKS3 Final Verification & Client API Readiness

تاریخ: 2026-11-20 · نسخه: 0.2.2 (بدون تغییر) · مبنا: `e3d995f`

بررسی تکمیلی و مستقل. به گزارش قبلی اعتماد نشد: کد منبع خوانده و تمام موارد
با اسکریپت reproduction اجرایی آزمایش شدند.

---

## مرحله ۱: امنیت BKS3 — نتایج عملی

| مورد | نتیجه | شواهد اجرایی |
|---|---|---|
| اعتبارسنجی Header قبل از KDF | **تأیید** | rounds نامعقول (99,999,999) در **42ms** رد شد، بدون اجرای KDF |
| محدودیت rounds (100k–5M) | **تأیید** | `_derive_key` محدوده را چک میکند (`session.py:72`) |
| جلوگیری CPU-DoS | **تأیید** | همان 42ms — سقف 5M مانع PBKDF2 طولانی میشود |
| صحت AAD | **تأیید** | دستکاری بایتهای ۴،۵،۶،۹،۲۰،۲۵،۳۶ هدر → همگی رد شدند |
| Authentication Tag | **تأیید** | GCM tag توسط `cryptography` تأیید میشود |
| پارامترهای نامعتبر | **تأیید** | هدر ناقص (۵،۸،۲۰،۳۶،۳۷ بایت) → `SessionError` |
| Downgrade BKS3→BKS2 | **تأیید** | تغییر mode `\x03`→`\x02` → رد شد (AAD) |
| خرابی/نقص Header | **تأیید** | تمام موارد `SessionError` امن، بدون exception خام |
| سازگاری BKS1/BKS2 | **تأیید** | migration v1→v3 و v2→v3 موفق، توکنها سالم، بکاپ بایت-دقیق |
| عدم ازدستدادن اطلاعات در migration | **تأیید** | rollback موفق، BKS3→BKS3 idempotent |

**ادعاهای امنیتی فقط با شواهد بالا مطرح میشوند.** چیزی فراتر از آن ادعا نمیشود.

---

## مرحله ۲: Migration

| مسیر | نتیجه |
|---|---|
| BKS1 → BKS3 | موفق، توKEN سالم، بکاپ بایت-دقیق |
| BKS2 → BKS3 | موفق، توکن سالم، بکاپ بایت-دقیق |
| BKS3 → BKS3 | idempotent (`False`)، `needs_migration=False` |
| Rollback | موفق، بایت به بایت |
| Backup | 0600، قبل از تغییر |
| بازیابی پس از شکست | تستشده (مرحله قبل) |

**نام `migrate_to_v2`**: عمداً حفظ شد. تغییر نام آن یک API-breaking change بود
که ممنوع است. مستندات اکنون صریحاً میگویند که این تابع به BKS3 ارتقا میدهد
(`docs/SESSION_SECURITY_AUDIT.md` بهروز شد).

---

## مرحله ۳: قفل بین Processها — یافته قطعی

**آزمایش عملی**: دو process همزمان، هر کدام ۵ نویسنده → انتظار ۱۱ اکانت،
**تنها ۶ اکانت باقی ماند** → **Lost Update اثبات شد**.

- `RLock` فعلی فقط داخل process کار میکند.
- `os.replace` اتمیک است ولیFromFile را تضمین نمیکند: هر process نسخه قدیمی cache
  را میخواند، تغییر میدهد و با نسخه خود جایگزین مینماید.
- **تصمیم**: اضافه کردن file lock (fcntl/msvcrt) در این مرحله **انجام نشد** —
  ریسک deadlock، قفل دائمی و پیچیدگی cross-platform نیازمند طراحی و benchmark
  جداگانه است (مأموریت صریحاً اجازه مستندسازی محدودیت را میدهد).
- **مستندسازی دقیق**: قفل between-process **NOT_IMPLEMENTED** است. کاربرد فعلی
  (یک process، چند coroutine/thread) کاملاً ایمن است. چند process نیازمند
  قفل فایل سیستمی است.

---

## مرحله ۴: آمادگی Client API

| قابلیت | وضعیت | پروتکل معتبر؟ | منبع aiobale | نیاز به ترافیک واقعی؟ | Mock کافی؟ | مانع |
|---|---|---|---|---|---|---|
| Media Download | **NOT_IMPLEMENTED** | خیر | فقط شماره فیلد `GetNasimFileUrl` | بله (رفتار URL) | خیر | متد `download_file` در SelfBot وجود ندارد |
| Media Resume | **NOT_IMPLEMENTED** | خیر | خیر — `chunkSize` فقط upload است | بله | خیر | هیچ پروتکل resumeای وجود ندارد |
| Inline Callback | **NOT_IMPLEMENTED** | خیر | فقط send-side `callbackData` | بله | خیر | RPC پاسخ callback در SelfBot وجود ندارد |
| Dialog Pagination | **PARTIAL** | خیر | شماره فیلدها مطابقت دارند | بله (معنای cursor) | تا حدی | کد + mock سالم، semantics تأییدنشده |
| Request Correlation | **PARTIAL** | خیر | خیر — `REQ_ID_FIELD=1` حدس است | بله | خیر | پیشفرض `strict` امن ولی بدون correlationworking |
| Live Testing | **BLOCKED** | خیر | خیر | بله | خیر | بدون حساب مجاز + نقص fixture (اصلاح شد) |

### شواهد پروتکل — حقیقت صادقانه
**هیچ تأیید پروتکل سرور بله در مخزن وجود ندارد.** `tests/fixtures/aiobale_methods/`
فقط تعاریف متدها را دارد (بدون framing/transport/req_id). تطابق 72/72 یک
**source-to-source** مقایسه با کتابخانه شخص ثالث است، نه مشاهده سرور.
هیچ `.pcap`، `.proto` یا ترافیک ضبطشده وجود ندارد.

### تضاد حلنشده
`badking/hybrid/auth.py:52` از `F_CODE = 3` و `schema.py` + fixture از
`ValidateCode.code = 2` استفاده میکنند — بدون ترافیک واقعی قابل حل نیست.

### مشکل اصلاحشده در Live Harness
`tests/integration/test_self_client_live.py` دو نقص واقعی داشت:
1. fixture آسنکرون با `@pytest.fixture` → بجای SelfBot، `async_generator` به تستها
   میرسید (عملاً ۵ تست با credential **Error** میدادند).
2. `SelfBot(ack_risk=True)` — پارامتر وجودنداشت → TypeError.

پس از اصلاح (`@pytest_asyncio.fixture` و حذف `ack_risk`): بدون credential ۵ SKIP،
با credential جعلی ۵ SKIP (connect failure) — **هیچ Error و هیچ PASS کاذب**.

---

## مرحله ۵: نتایج تست و وضعیت

- تمام تستها (آفلاین): **۱۲۷۶ پاس، ۱ SKIP، ۶ deselected** (پیش از اصلاح live harness)
- Live harness: بدون credential ۱ پاس + ۵ SKIP؛ با credential جعلی ۱ پاس + ۵ SKIP
- CI Run #38 سبز روی Python 3.9–3.12

---

## نتیجه نهایی و پیشنهاد مرحله بعد

**زیرساخت Session برای شروع توسعه قابلیتهای اصلی Client API آماده است:**
رمزنگاری، migration، atomic write و همزمانی تک-process همگی تأیید و تستشدهاند.

**اما توسعه Client API نمیتواند به طور کامل بدون ترافیک واقعی پیش برود.**
پیشنهاد مرحله بعد به ترتیب:

1. **Media Download (SelfBot)** — تنها قابلیتی که شماره فیلدهایش از منبع معتبر
   (aiobale fixture) موجود است؛ قابل پیادهسازی بدون حدس RPC، ولی تأیید نهایی
   live میماند.
2. **رفع تضاد auth `code=2` vs `3`** — نیازمند ترافیک واقعی یا `.proto`.
3. **Live harness** — اکنون سالم است؛ با یک حساب آزمایشی مجاز، اولین تأیید
   واقعی پروتکل (framing, correlation, cursor) ممکن میشود.
4. **Media Resume / Inline Callback / Correlationwire** — BLOCKED تا زمانی که
   شواهد پروتکل واقعی بدست آید.

**ارزیابی Production**: Session Storage بله (با استثنای قفل between-process)؛
Client API خیر — هیچ قابلیتی live-verified نیست.
