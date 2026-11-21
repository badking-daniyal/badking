# Changelog

همه تغییرات قابل توجه این پروژه در این فایل ثبت می‌شود.

قالب بر اساس [Keep a Changelog](https://keepachangelog.com/fa/1.1.0/)، و
نسخه‌گذاری بر اساس [Semantic Versioning](https://semver.org/lang/fa/).

---

## [Unreleased]

### Fail-Closed Hardening & Transport Review (2026-11-21)
- آسیبپذیری Fail-Open رفع شد: پیشتر شکست DNS / پاسخ خالی / رکورد نامعتبر به `transport=None` و سپس AsyncClient معمولی بدون IP Pinning منتهی میشد. اکنون تمام این مسیرها استثنا میدهند و تنها AsyncClientای ساخته میشود که transport پینشده دارد.
- `resolve_validated_ips` رکورد DNS نامعتبر و پاسخ خالی را صریحاً رد میکند؛ `build_pinned_transport` هرگز `None` برنمیگرداند.
- `PinnedAsyncTransport` رسماً subclass از `httpx.AsyncBaseTransport` شد (قرارداد صریح، ایمن در صورت نبود httpx).
- وابستگی به API داخلی httpx/httpcore (`AsyncResponseStream`، `AutoBackend`) مستند و با تست سازگاری پوشش شد.
- تستهای جدید: `tests/test_ssrf_fail_closed.py` (6) و `tests/test_ssrf_transport_compat.py` (7) — اثبات صفر AsyncClient بدون pinning هنگام شکست DNS، ریدایرکت ناامن، Cancellation و عدم باقی ماندن Task.
- تستها: ۱۴۷۶ پاس + ۶ SKIP. نسخه 0.2.2 بدون تغییر.

### Download SSRF / DNS Rebinding Protection (2026-11-21)
- آسیبپذیری واقعی DNS Rebinding در دانلود رسانه رفع شد: پیشتر `validate_download_url` تنها DNS را چک میکرد و httpx دوباره resolve میکرد.
- ماژول جدید `badking/hybrid/ssrf.py` با `PinnedAsyncBackend` و `PinnedAsyncTransport`: اتصال دقیقاً به IP تأییدشده میرود، hostname اصلی در Origin میماند تا Host/SNI و اعتبارسنجی گواهی حفظ شوند.
- `trust_env=False` و transport صریح: متغیرهای `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` نمیتوانند مسیر پینشده را دور بزنند.
- رنجهای خطرناک تکمیل شدند: CGNAT (`100.64.0.0/10`)، `192.0.0.0/24`، benchmarking، IPv4-mapped IPv6، userinfo و پورتهای داخلی مسدود میشوند.
- ریدایرکت هر مرحله دوباره اعتبارسنجی و پین میشود؛ Timeout کلی، سقف حجم و نوشتن اتمیک دستنخورده ماندند.
- ۴۲ تست امنیتی جدید: `tests/test_ssrf_ip_pinning.py`، `tests/test_ssrf_live_socket.py` (سرور محلی واقعی — اثبات اتصال به IP پینشده و حفظ Host header)، `tests/test_ssrf_download_integration.py`.
- مستندات: `docs/DOWNLOAD_SSRF_AUDIT.md`. تستها: ۱۴۶۰ پاس + ۶ SKIP.

### Client API Correctness & Protocol Audit (2026-11-21)
- رفع ۵ باگ واقعی در `iter_messages`/`iter_dialogs` و Message Parsing:
  - صفحه کاملاً تکراری دیگر پیمایش را زود متوقف نمیکند (cursor با پیشرفت ایمن جلو میرود).
  - پیام با `messageId=0` بهاشتباه تکراری تلقی نمیشد (شمارنده یکتای سراسری).
  - `limit` حتی اگر سرور بیشتر از تعداد درخواستی برگرداند رعایت میشود.
  - دیالوگ تکراری بین صفحات فیلتر میشود؛ کلید یکتا `(peer.type, peer.id)` است.
  - `_parse_message` حالا تمام انواع محتوا (text/document/service/bot/gift/empty) و `repliedTo`/`editedAt` را میخواند؛ متن سند/سرویس/ربات/گیفت گم نمیشد.
  - `_parse_dialog` عنوان، username و آخرین پیام سند را میخواند.
- اصلاح schema: تعریف تکراری `GiftPacket` (scalar) حذف شد؛ `ServiceMessage`، `ServiceExt`، `GiftOpened`، wrapperهای `StringValue`/`BoolValue` و ساختار `repliedTo`/`previousMessage`/`nextMessage` طبق aiobale 0.3.9 اضافه شدند (منبع مقایسه، نه اثبات پروتکل رسمی).
- ۵۱ تست مستقل آفلاین (`tests/test_client_api_correctness.py`) شامل pagination چندصفحهای، مرز صفحات، پاسخ ناقص/خراب، تکرار، cancellation، timeout، parsing و round-trip باینری. تست معیوب cancellation که بیانتها گیر میکرد اصلاح شد (ref اضافه + `asyncio.wait_for`).
- تستها: ۱۴۱۸ پاس + ۶ SKIP.

### Bot API Multipart File Upload (2026-11-21)
- `send_photo`/`send_document`/`send_audio`/`send_video`/`send_voice`/`send_animation` حالا مسیر فایل محلی را میپذیرند و طبق مستندات رسمی بله درخواست `multipart/form-data` میفرستند. file_id و URL همچنان JSON میمانند (رفتار قبلی حفظ شد).
- باگ: در حالت multipart، `reply_markup` و سایر اشیاء JSON بهصورت `str(dict)` ارسال میشدند (فرمت پایتونی، نه JSON). حالا با `json.dumps` سریالایز میشوند.
- پیش از این تغییر، هیچ متدی Bot API پارامتر `files` را پرتاب نمیکرد — آپلود فایل عملاً پیاده نشده بود.
- ۶ تست که شکل واقعی درخواست را میسنجند (`tests/test_bot_multipart_upload.py`) + مستندات `docs/bale-api.md`.

### Slow HTTP Trickle Protection (2026-11-21)
- `write_stream_atomic(deadline=...)` — مهلت مطلق (wall-clock) کل دانلود؛ برخلاف `timeout` شبکه که per-operation است.
- `SelfBot.download_file(total_timeout=600)` — پیشفرض ایمن، قابل تنظیم، `None` = رفتار قبلی.
- سرور کند (یک بایت در هر چند ثانیه) بعد از مهلت متوقف میشود و فایل موقت پاک میشود — فایل مقصد دستنخورده میماند.
- ۴ تست (`tests/test_slow_trickle.py`) + مستندات `docs/MEDIA_DOWNLOAD.md`. DNS Rebinding صریحاً BLOCKED باقی ماند (نیاز به IP pinning).

### SelfBot Inline Keyboard (2026-11-21)
- `SelfBot.send_message()` پارامتر `reply_markup` میگیرد — ارسال inline keyboard از اکانت شخصی (source-confirmed from aiobale 0.3.9).
- اسکیمای `InlineKeyboard` به ساختار واقعی پروتکل اصلاح شد: `InlineKeyboardMarkup{1:[Row{1:[Button]}]}`، دکمهها `text=1, url=2{wrapper}, callbackData=3{wrapper}, copyText=9{wrapper}`. `make_inline_keyboard` قبلی ساختار غلط `rows` داشت و هرگز استفاده نمیشد.
- `make_text_content(text, reply_markup, temp_id)` زنجیره `MessageContent{13: TemplateMessage{1,2,5}}` را میسازد.
- **محدودیت صریح**: callback query در پروتکل داخلی SelfBot وجود ندارد (هیچ update/RPC در aiobale 0.3.9) — هیچ `on_callback` حدسی اضافه نشد.
- ۱۲ تست آفلاین (`tests/test_inline_keyboard.py`) + مستندات `docs/SELF_INLINE_KEYBOARD.md`. وضعیت Live-verified: BLOCKED (بدون حساب آزمایشی).

### Beta Hardening — Independent Audit Fixes (2026-11-20)
- **سه ممیزی مستقل** (Client/Bot API، امنیت، تست/مستندات/CI) مستقیماً از کد خوانده شد؛ ادعاهای reports قبلی دوباره تأیید شدند.
- **باگهای Client API رفعشده**: `get_pinned()` کلید پاسخ اشتباه (`pins_data` → `data`)؛ `edit_message()` تشخیص موفقیت بر اساس فیلد nonexistent؛ `stop_typing()` و `set_online()` فیلدهای اجباری `typing_type`/`timeout`؛ `add_contact()` پارامتر بیاثر (مستند شد چون پروتکل جای name ندارد).
- **امنیت**: deny-by-default واقعی در `PermissionPolicy` (نقشه کامل ۳۲ RPC state-changing)؛ جلوگیری SSRF با `validate_download_url` و ریدایرکت دستی validateشده؛ نامهای رزرو ویندوز؛ هش کردن شماره تلفن در DEBUG log؛ `doctor` فقط ۴ کاراکتر آخر توکن؛ Secret scanner شامل untrackedها.
- **مستندات/مثالها**: حذف متدهای وجودنداشته (`ack_risk`, `disconnect`, `on_self_*`, `idle`, `login`) از مثالهای ۱۱–۱۴ و README فارسی/انگلیسی.
- **تستها**: ۳۷ Regression test جدید (`tests/test_beta_hardening.py`)؛ ۱۳۴۴ پاس + ۱ SKIP، exit 0. نسخه 0.2.2 بدون تغییر، PyPI منتشر نشد.
- **BLOCKED باقی**: Request Correlation، Media Resume، JWT verification، Live verification — بدون شواهد پروتکل/حساب آزمایشی حدسی نزده شد.

### Media Download in SelfBot (2026-11-20)
- **تصحیح باگ پروتکلی**: `NESTED["FileURL"]` از `{url:1,name:2,size:3}` به مقادیر تأییدشده aiobale 0.3.9 `{fileId:1,url:2,timeout:3,chunkSize:7}` اصلاح شد؛ `FileInfo.fileStorageVersion=3` اضافه شد.
- ماژول `badking/hybrid/download.py`: sanitize نام فایل، جلوگیری Path Traversal، `base_dir` بهعنوان مرز، فایل تکراری `(1)`، نوشتن اتمیک `.part` + fsync + `os.replace`، پاکسازی در شکست، جریان چانکبهچانک (بدون بارگذاری کامل در RAM)، محدودیت حجم قابل تنظیم.
- `SelfBot.get_file_url()` و `SelfBot.download_file()` + `Message.media_info()` / `Message.download()`.
- ۳۱ تست آفلاین (`tests/test_media_download.py`) شامل پروتکل، traversal، فایل خالی/بزرگ، قطع اتصال، timeout، مجوز، تکرار، همزمانی.
- مستندات `docs/MEDIA_DOWNLOAD.md`; `asyncio_mode=auto` در pytest.ini (تحت پوشش تستهای موجود).
- ۱۳۰۷ پاس، ۱ SKIP، exit 0. نسخه 0.2.2 بدون تغییر، PyPI منتشر نشد. رفتار واقعی سرور BLOCKED (بدون حساب آزمایشی).

### BKS3 Final Verification & Client API Readiness (2026-11-20)
- ممیزی مستقل BKS3: تمام موارد امنیتی (AAD، tag، downgrade، DoS، هدر ناقص، migration) با شواهد اجرایی تأیید شد.
- **Lost update بین دو process اثبات شد** (۶ باقی ماند از ۱۱ انتظار) — قفل between-process صریحاً NOT_IMPLEMENTED و مستند شد.
- **رفع نقص live harness**: `@pytest_asyncio.fixture` و حذف `ack_risk` نامعتبر — با credential بجای ۵ Error، ۵ SKIP میدهد.
- بهروزرسانی `docs/SESSION_SECURITY_AUDIT.md` به BKS3/600k؛ سند `docs/BKS3_FINAL_VERIFICATION.md`.
- ارزیابی Client API: Media Download تنها قابلیت قابل پیادهسازی بدون حدس RPC؛ بقیه BLOCKED تا ترافیک واقعی.
- نسخه 0.2.2 بدون تغییر، PyPI منتشر نشد.

### Session Storage Hardening (2026-11-20)
- **PBKDF2 versioned**: فرمت ``BKS3`` با 600k iteration و تعداد rounds داخل هدر (محافظت شده توسط AAD). فایلهای ``BKS2`` قدیمی (200k) همچنان قابل خواندن و قابل ارتقا با `migrate_to_v2()` — مهاجرت تدریجی و سازگار.
- **Atomic writes مقاوم**: فایل موقت منحصربهفرد، مجوز 0600، flush + fsync فایل، `os.replace` اتمیک، fsync پوشه (جایی که پشتیبانی شود)، پاکسازی موقت در شکست. فایل اصلی در تمام سناریوهای شکست حفظ میشود.
- **قفل per-path (RLock)**: save/load/migrate/rollback/backup/get/put/delete تحت قفل — جلوگیری از lost update و race در همان process. محدودیت: قفل بین processها کار نمیکند (مستند شده).
- ۱۷ تست regression جدید (crash پیش/پس replace، شکست fsync، فایل موقت خراب، permission، session ناقص، همزمانی save/migrate/rollback، reentrancy).
- `benchmarks/bench_session.py` قابلتکرار — نتایج در `docs/SESSION_STORAGE_HARDENING.md`.
- **۱۲۷۶ پاس + ۱ SKIP + ۵ live SKIP**. نسخه 0.2.2 بدون تغییر، PyPI منتشر نشد.

### Independent Security Review (2026-11-20)
- **۶ نقص اثباتشده اصلاح شد** (همه با اسکریپت reproduction تأیید و با regression تست پوشش داده شدند):
  - rollback بکاپ خراب، فایل سالم را با داده ناخوانده جایگزین میکرد → validate کامل بکاپ
  - `AttributeError` خام از `Session.from_dict` → `SessionError` امن
  - نشت توکنها در `repr(Session)` → `repr=False` برای فیلدهای حساس
  - تزریق session plaintext بدون رمز → خواندن plain فقط با `allow_plain` صریح
  - FIFO پاسخ دیرهنگام/آپدیت ناخواسته را اشتباه تخصیص میداد → پیشفرض `strict`
  - فایل session با مجوز 0644 ساخته میشد → نوشتن با `0600`
- تست `test_transport_payload_untouched_by_default` از tautology به تست واقعی تبدیل شد
- ۱۰ تست regression جدید — **۱۲۵۹ پاس + ۱ SKIP + ۵ live SKIP**
- سند `docs/INDEPENDENT_SECURITY_REVIEW.md` — ارزیابی صادقانه Production (آماده نیست)
- نسخه 0.2.2 بدون تغییر، PyPI منتشر نشد

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
