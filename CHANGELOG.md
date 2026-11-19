# Changelog

همه تغییرات قابل توجه این پروژه در این فایل ثبت می‌شود.

قالب بر اساس [Keep a Changelog](https://keepachangelog.com/fa/1.1.0/)، و
نسخه‌گذاری بر اساس [Semantic Versioning](https://semver.org/lang/fa/).

---

## [Unreleased]

### Planned
- `RedisStorage` و `PostgreSQLStorage` برای FSM
- سیستم افزونه (`badking.plugins`)
- بومی‌سازی (`badking.i18n`) با فارسی و انگلیسی
- Migration Toolkit برای مهاجرت از aiobale
- ۲۰ نمونه پروژه کامل

---

## [0.1.0] — 2026-11-19

اولین نسخه. هسته کامل، لایه self-bot کامل، ۵۲۲ تست آفلاین.

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
- ۵۲۲ تست، همه آفلاین
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
