# Changelog

همه تغییرات قابل توجه این پروژه در این فایل ثبت می‌شود.

قالب بر اساس [Keep a Changelog](https://keepachangelog.com/fa/1.1.0/)، و
نسخه‌گذاری بر اساس [Semantic Versioning](https://semver.org/lang/fa/).

---

## [Unreleased]

### Session Security & Live Client Validation (2026-11-20)
- **Session Encryption به AES-256-GCM (AEAD) ارتقا یافت** — فرمت نسخهبندی شده `BKS2`، nonce تصادفی ۱۲ بایتی، Authentication Tag، AAD روی header، PBKDF2-SHA256 200k
- Migration امن و کنترلشده: تشخیص فرمت قدیمی، بکاپ `0600`، `migrate_to_v2` idempotent، `rollback_migration` بایت به بایت، بدون از دست رفتن داده در شکست
- خواندن فرمتهای قدیمی `BKS1` (plain و XOR+HMAC) حفظ شد — sessionهای موجود نشکستند
- خطاهای خراب session به `SessionError` امن تبدیل میشوند (بدون افشای محتوا)
- وابستگی `cryptography>=42` به extras `hybrid` / `all`
- **رفع باگ پروتکل:** `req_id` دیگر پیشفرض روی فیلد ۱ payload نوشته نمیشود (فیلد ۱ داده واقعی است) — correlation داخلی FIFO جایگزین شد
- **رفع باگ `iter_dialogs`:** cursor از `sortDate` به جای شمارش ردیف، با محافظت چرخه
- زیرساخت Live Testing واقعی: ۵ تست opt-in، ماسک اطلاعات حساس، بدون عملیات مخرب (بدون حساب → SKIP)
- ۲۲ تست Session security + ۴ تست Client API audit — نسخه 0.2.2 بدون تغییر، PyPI منتشر نشد

### Security Completion Phase (2026-11-20)
- **JWT Verification واقعی** با PyJWT — الگوریتم محدود، جلوگیری از Algorithm Confusion، رد none/malformed/expired/nbf/iss/aud، خطاهای امن بدون نشت توکن
- `OTPGuard` حالا در `AuthFlow` و `SelfBot.connect` استفاده میشود (حالت blind: تلاش/انقضا/replay؛ صحت کد توسط سرور)
- JWT verification در مسیر مصرف توکن (`sign_in`, `refresh`, `connect`) وصل شد
- وابستگی `PyJWT>=2.8,<3` به extras `hybrid` / `all`
- ۴۲ تست امنیتی جدید — **۱۲۲۵ پاس + ۵ live SKIP**
- نسخه 0.2.2 بدون تغییر، PyPI منتشر نشد

### FINAL Security & Engineering Validation (2026-11-20)
- **Critical:** تناقض `permissions=None` رفع شد — پیشفرض Deny by Default، Legacy فقط با `legacy_unrestricted=True` + هشدار
- `OTPGuard` اضافه شد: محدودیت تلاش، انقضا، جلوگیری از replay (کد هش میشود)
- Secret scanner اجباری CI (`scripts/ci_secret_scan.py`) + تست اثربخشی واقعی `.gitignore`
- Migration: باگ import خیالی (`from badking import Command`) رفع شد — API خیالی ساخته نمیشود
- Benchmark نهایی: median/P95/stddev، ۴ اندازه ورودی، مقایسه با aiobale
- ۶ گزارش نهایی + تستهای مربوطه
- **تستها:** ۱۲۲۵ پاس + ۵ live SKIP. PyPI منتشر نشد، نسخه 0.2.2 بدون تغییر

### Planned
- انتشار روی PyPI
- تست زنده self-bot (نیاز به شماره واقعی)
- ۳۹ subsection مستندات به صفحات جداگانه

---

## [Unreleased] — Optimization & Security Hardening

- Secret audit: git history clean, backup.zip tokens BLOCKED (rotate needed),
  .gitignore hardened, 	ests/test_secret_audit.py
- Serialization: uild() ~40% faster, encode_named() ~31% faster,
  binary equivalence verified with 700+ inputs
- enchmarks/bench_serialization.py with warm-up, median/P95/P99, memory
- Self Client RBAC, OTP validation, secure logging, session expiry + 33 tests
- Reliability: RPC error mapping, flood wait, correlation + 17 tests
- Migration status clarified: import only, balethon decorators NOT_IMPLEMENTED
- 5 new reports; 1153 tests passing; no PyPI release, version unchanged

---

## [Unreleased] — Real-World Validation

- docs/PROTOCOL_VERIFICATION.md: 72/72 field numbers verified against
  real aiobale 0.3.9 source (fixture committed with MIT license)
- 	ests/test_protocol_verification.py: 16 tests, no guessing
- 	ests/integration/: 14 mock integration tests + 4 live tests SKIP (BLOCKED)
- docs/REAL_WORLD_TESTING.md, docs/COMPETITIVE_BENCHMARK.md,
  docs/SECURITY_REVIEW.md
- Honest benchmark: BADKING import 2.5x faster, serialization 4x slower
- 1078 tests passing, 4 live skipped. No PyPI release.

---

## [0.2.2] — 2026-11-20

سه اولویت مأموریت: Self Client audit، Migration validation، ۳۹ صفحه مستندات.

### Added
- docs/SELF_CLIENT_AUDIT.md — ممیزی مستقل ۳گانه با یافتههای VERIFIED/BLOCKED
- docs/MIGRATION_VALIDATION.md — اعتبارسنجی ۴/۴ فایل پروژه واقعی aiobale
- docs/REMAINING_GAPS.md — کمبودهای صادقانه
- docs/guide/ — ۳۹ صفحه مستقل + نمایه، تستشده در برابر API واقعی
- BaleMethod — لایه سازگاری متد سفارشی aiobale
- ۴۰ regression test جدید (self client audit, bale method, guide docs, reports)

### Fixed (یافتههای ممیزی Self Client)
- _my_id قبل از session محاسبه میشد (get_me/is_out خراب)
- سرویس اشتباه wallet، متد مرده edit_profile، کلیدهای ناسازگار گروه/کاربر
- crash با date bytes، آپلود silent failure، probe فریبنده
- websockets محدود به <14.0

### Tests
- ۱۰۴۸ پاس (آفلاین)

---

## [0.2.1] — 2026-11-20

تکمیل Phase A–E سند مأموریت. ۱۰۰۱ تست، ۱۸۹ export.

### Added
- **Security Scanner** (`badking.security.SecurityScanner`) — تشخیص توکن،
  کلید خصوصی، eval/exec، shell=True، SSL disabled، silent exception،
  assert با severity CRITICAL→INFO. CLI: `badking security scan . --json`
- **`migration/mappings.json`** — نگاشت واقعی aiobale→BADKING با ۴ وضعیت،
  تستشده در برابر کد (هیچ هدف خیالی)
- **`docs/IMPLEMENTATION_STATUS.md`** — وضعیت صادقانه ۳۵ بخش مأموریت
- **`docs/MASTER_AUDIT_REPORT.md`** — خروجی Phase 1
- **`docs/COMPETITIVE_ANALYSIS.md`** — مقایسه واقعی، بدون ادعای تأییدنشده
- **`docs/API_REFERENCE.md`** — مرجع سریع، تستشده در برابر API واقعی
- **`docs/BENCHMARK.md`** + `benchmarks/bench_core.py` — نتایج واقعی
- **Bot API:** `send_sticker`, `send_poll`, `ban/unban/restrict_chat_member`,
  `send_media_group`, `get_chat_member_count`
- **Message:** `reply`, `delete` aliases
- **Bot-first API:** `on_message`, `on_callback`, `run`, `dispatcher`
- **BaseMiddleware** — پل الگوی کلاسمحور به middleware تابعی

### Fixed
- ۲۰ نمونه از APIای استفاده میکردند که وجود نداشت (`bot.run`, `@bot.on_message`,
  `message.reply`) — رابط به کتابخانه اضافه شد، نه نمونهها بازنویسی
- نگاشت `answer_poll → send_poll` به متدی اشاره میکرد که نبود — اضافه شد
- نگاشت `BaseMiddleware` دروغ میگفت — کلاس پیاده شد
- چهار نوع کیبورد در سطح بالا export نبودند — اضافه شدند

### Tests
- ۱۰۰۱ پاس (آفلاین)
- تستهای جدید: `test_security_scanner`, `test_migration_mapping`,
  `test_mission_docs`, `test_example_api`, `test_session_control`

---

## [0.2.0] — 2026-11-19

بستن شکاف‌های طرح. ۹۱۵ تست آفلاین، ۱۷۶ export، ۲۷ نمونه.

### Added

**ذخیره‌سازی پیشرفته**
- `RedisStorage` — وضعیت FSM روی Redis، با TTL، پیشوند کلید، `health()`،
  `ttl_left()`، `clear()`. برای اجرا روی چند سرور.
- `PostgreSQLStorage` — وضعیت روی Postgres، با TTL، `purge_expired()`،
  `count()`، Connection Pool. نام جدول اعتبارسنجی می‌شود (SQL Injection).
- هر دو بدون وابستگی اجباری: اگر پکیج نصب نباشد، خطای روشن با دستور نصب
  می‌دهند، نه `ImportError` گنگ.

**Media Engine** (`badking.media.MediaEngine`)
- دانلود با پیشرفت، آپلود با تشخیص خودکار نوع، کش بر اساس هش
- `safe_filename()` — حذف Path Traversal، کاراکتر خطرناک ویندوز، نام بلند
- `validate_extension()` — فقط پسوندهای مجاز؛ `.exe`، `.sh`، `.bat` رد می‌شوند
- `check_mime_matches()` — فایل با MIME ناسازگار رد می‌شود
- `enforce_disk_limit()` — قدیمی‌ترین‌ها پاک می‌شوند
- `download_many()` با محدودیت هم‌زمانی؛ خطای یکی بقیه را متوقف نمی‌کند

**Moderation Engine** (`badking.moderation.Moderator`)
- `Rule` با regex، کلمات ممنوع، حداکثر طول/لینک/فایل/منشن
- اقدام‌ها: اخطار، سکوت، اخراج، لگد، حذف
- تشدید خودکار: سه اخطار → اخراج
- لیست سفید و سیاه، معافیت ادمین، تاریخچه در Storage
- قواعد آماده: `link_rule`، `flood_rule`، `mention_spam_rule`، `word_rule`

**Channel Monitor** (`badking.moderation.ChannelMonitor`)
- ثبت ورود و خروج، آمار روزانه، رشد خالص، نرخ ریزش
- چند کانال، چند ادمین، گزارش خوانا
- پایدار در Storage، بازیابی با `load()`

**Migration Toolkit** (`badking.compat`)
- `badking migrate` — تبدیل پروژه aiobale بدون بازنویسی
- importها، متدها، و **اسم‌ها در بدنه** (وگرنه `NameError`)
- هر چیزی که خودکار نشد، در گزارش می‌آید. حدس نمی‌زند.
- `--dry-run`، نسخه پشتیبان `.bak`، خروجی JSON
- BOM ویندوز تحمل می‌شود

**مستندات دو زبانه**
- `docs/fa/README.md` و `docs/en/README.md`
- تست `tests/test_docs.py`: تعداد بخش‌ها، ساختار کد، هر import در مستندات
  باید واقعاً در کتابخانه باشد، هر دستور CLI باید واقعاً وجود داشته باشد

**نمونه‌های جدید**
- `23_moderation.py` — مدیریت گروه با تاریخچه
- `24_migrate.py` — مهاجرت از aiobale
- `25_media.py` — دانلود، آپلود، کش
- `26_redis.py` — چند سرور با Redis
- `27_plugins.py` — افزونه سفارشی و دو زبان

### Changed
- `build_parser()` از `main()` جدا شد تا CLI بدون اجرا تست شود
- `pyproject.toml`: extras `postgres` و `all`، نویسنده واقعی
- `Rule`: پیش‌فرض محدودیت‌ها `-1` شد تا `max_files=0` («هیچ فایلی مجاز
  نیست») از «این شرط را نگذار» قابل تفکیک باشد

### Fixed
- `Moderator._call` کوارگ نمی‌پذیرفت؛ `until_date` سکوت اعمال نمی‌شد
- `daily_breakdown` رویدادهای لبه «همین حالا» را جا می‌انداخت
- `Path.write_text(newline=...)` روی پایتون ۳.۹ کار نمی‌کند
- `Callable[[int, int], Awaitable[None] | None]` روی ۳.۹ در زمان اجرا خطا
  می‌داد؛ به `Union` تغییر کرد

---

## [0.1.0] — 2026-11-19

اولین نسخه. هسته کامل، لایه self-bot کامل، ۶۳۶ تست آفلاین.

### Added

**هسته**
- `Bot`، `Dispatcher`، `Router` با زیرروتر و اولویت هندلر
- `F` — Magic Filter با عملگرهای `&`، `|`، `~` و فیلتر ناهمگام
- FSM: `State`، `StatesGroup`، `FSMContext` با `MemoryStorage` و `SQLiteStorage`
- Middleware: لاگ، متریک، ضد اسپم، و میدل‌ور سفارشی

**تاب‌آوری**
- `RetryPolicy` با backoff ثابت/خطی/نمایی، jitter، و احترام به `retry_after` سرور
- `CircuitBreaker` با حالت‌های closed/open/half-open
- `RequestQueue` با سقف هم‌زمانی، نرخ، و فشار ورودی
- `ResilientCaller` که هر سه را با ترتیب درست ترکیب می‌کند

**خطاها**
- سلسله‌مراتب ۴۰+ کلاسه با ریشه `BADKINGError`
- هر خطا `error_code`، `method`، `hint` و `retryable` دارد
- `diagnose()` گزارش آماده Issue می‌سازد
- `format_exception()` توکن و کلید هگز را از لاگ پاک می‌کند

**لایه Self-bot / Internal API**
- ۷۹ متد RPC با شماره فیلد واقعی، تطابق کامل با کلاینت رسمی بله
- ۶۵ اسکیمای پاسخ
- ورود با شماره و کد SMS، تاریخچه، ارسال، واکنش، گروه، کانال، مخاطبین، کیف پول
- `raw_call()` برای متد ناشناخته، `probe()` برای کشف متد، `describe()` و `search()`
- اسکیما قابل override با `BADKING_RPC_SCHEMA` — بدون آپدیت کتابخانه

**پروتکل و ابزار**
- `enums/` — ۱۶ enum پروتکل با نام‌های جایگزین کلاینت رسمی
- `utils/` — برش هوشمند متن، شناسه، لینک، کدک int64، `Throttle`، نوار پیشرفت،
  نرمال‌سازی شماره فارسی
- `CallbackData` تایپ‌دار بدون pydantic
- `InlineKeyboardBuilder`، `ReplyKeyboardBuilder`، `KeyboardPaginator` با `parse()`

**زیرساخت**
- `JobQueue`، `Scheduler`، `EventBus`، `Store` (ORM سبک)
- `Metrics` با خروجی Prometheus
- `AntiSpam`، `AuditLog`، `Captcha`، `RBAC`، `Secrets`
- `DryBot` برای تست بدون توکن، `Health` برای health check
- `AIAssistant`، `SimpleRAG`، `OpenAICompatibleLLM`، `IntentRouter`
- `PaymentToolkit`، `SafirClient`، `BusinessBot`
- `Flow` — ساخت ربات بدون کد با JSON
- `Conversation` — ویزارد مکالمه چندمرحله‌ای

**CLI**
- `badking new` — ساخت پروژه
- `badking doctor` — بررسی سلامت محیط با راه‌حل برای هر خطا
- `badking info` — نسخه، تعداد RPC، دسترسی قابلیت‌ها
- `badking check` — بررسی نحوی پروژه
- `badking test` — اجرای تست‌ها
- `badking login` — ورود self-bot
- `badking rpc` — لیست، جستجو و توصیف متدهای RPC
- `badking dry-run`، `badking codegen`، `badking run`، `badking setup`

**تست**
- ۶۳۶ تست، همه آفلاین
- `test_public_api.py` سطح عمومی را در دو جهت می‌پاید

### Security
- توکن و کلید هگز در `format_exception()` پاک می‌شوند
- لایه self-bot پیش‌فرض خاموش است و `ack_risk=True` می‌خواهد
- هیچ اطلاعات محرمانه‌ای در لاگ پیش‌فرض نوشته نمی‌شود

---

## قالب نسخه‌گذاری

- **MAJOR** — تغییر ناسازگار. Migration Guide همراه آن می‌آید.
- **MINOR** — قابلیت جدید سازگار با قبل.
- **PATCH** — رفع باگ.

هیچ API عمومی بدون یک نسخه MINOR هشدار حذف نمی‌شود.
