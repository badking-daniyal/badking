# نقشه راه BADKING — وضعیت نهایی (2026-11-18)

همه ۹ فاز پیادهسازی شدند. **87 تست پاساند** و بسته `badking-0.1.0-py3-none-any.whl` ساخته شد.

## ممیزی کیفیت (2026-11-18) ✅
پس از ممیزی سهگانه کد، ۳۳ یافته (۲ بحرانی، ۱۵ مهم، ۱۲ جزئی + ۴ بررسی) شناسایی و همگی رفع شدند:
- **بحرانی**: الگوریتم HMAC مینیاپ (data-check-string الفبایی + `\n`) مطابق مستندات رسمی + تست وکتور مستقل؛ OTP با `secrets` امن.
- **هسته**: offset بعد از پردازش هندلر پیشروی میکند (جلوگیری از گمشدن آپدیت)؛ `StopPropagation` صادر شد؛ storage پیشفرض در Dispatcher؛ `F.contains` ایمن؛ `download_file` با base_url و خطای شبکه؛ `is_command`؛ کالیبراسیون کسری نرخ.
- **امنیت**: جلوگیری از تزریق SQL در Store؛ بارگذاری مجدد AuditLog؛ Antispam سابقه پنجره را پاک نمیکند؛ `is_fresh`/`auth_date` در مینیاپ.
- **تخصصی**: خروجی Prometheus معتبر (یک `# TYPE` + escape label + prefix)؛ بررسی status در LLM؛ ایزولاسیون خطای ابزار و EventBus؛ retry در Connector (شامل 429)؛ نوشتن اتمیک offset؛ heappush بهجای heapify.
- تستهای قراردادی و رگرسیون new: `test_audit_critical.py`, `test_audit_regressions.py`, `test_callback.py`, `test_shop_cart.py`, `conftest.py`.

## فاز ۱ — پایه ✅
- [x] ساختار پروژه و pyproject
- [x] مدلهای Pydantic مطابق docs.bale.ai
- [x] ثابتهای قابلتنظیم + یادگیری از retry_after
- [x] خطاها (ok=false → exception)
- [x] Bot client + متدهای اصلی
- [x] Dispatcher / Router / Magic Filter F / middleware
- [x] Long Polling + ذخیره offset
- [x] سرور mock + ربات نمونه

## فاز ۲ — پایداری ✅
- [x] FSM (StatesGroup, State, FSMContext) + Memory/SQLite + timeout + migration
- [x] Rate Limit Engine (صف اولویت + backoff از retry_after)
- [x] Update Recovery (OffsetStore)

## فاز ۳ — قابلیتهای بله ✅
- [x] MiniApp + اعتبارسنجی HMAC initData
- [x] سفیر (OTP، قالب، رمزدار، idempotency، دکمهها)
- [x] پرداخت (sendInvoice، createInvoiceLink، answerPreCheckout، askReview، inquireTransaction)
- [x] Business API (مسیر جدا، ارسال فایل با file_id)

## فاز ۴ — هوش مصنوعی ✅
- [x] LLM قابلتعویض (OpenAI-compatible + EchoLLM)
- [x] حافظه بلندمدت + شخصیت
- [x] Tool Calling + Intent Router + RAG + نرمالسازی فارسی

## فاز ۵ — بدونکد ✅
- [x] Flow Builder (JSON → اجرا → خروجی کد)
- [x] CLI جادویی (new / dry-run / codegen)
- [x] Multi-platform Adapter (رابط مشترک)

## فاز ۶ — زیرساخت ✅
- [x] Connector عمومی (هر URL/متد/auth + retry + webhook امضاشده)
- [x] Scheduler/Cron + Job Queue
- [x] Event Bus + ORM ساده
- [x] Voice (STT/TTS) + OCR

## فاز ۷ — کیفیت ✅
- [x] Observability (لاگ JSON + Metrics Prometheus)
- [x] امنیت (Secrets/keyring، AntiSpam، Captcha، AuditLog، RBAC)
- [x] Dry-run + Health Check
- [x] Docker + CI/CD

## فاز ۸ — Hybrid و سازگاری ✅
- [x] لایه Hybrid ایزوله و غیرفعال پیشفرض + هشدار امنیتی
- [x] لایه سازگاری aiogram / python-telegram-bot

## فاز ۹ — انتشار ✅
- [x] صادرات 56 قابلیت در سطح بالا
- [x] LICENSE (MIT) + README فارسی
- [x] ساخت wheel + تست نهایی

## کارهای آتی اختیاری (post-release)
- [ ] Admin Web Panel با رابط گرافیکی
- [ ] پیادهسازی کامل RPC داخلی self-bot (پلاگین جدا، ریسک بالا)
- [ ] Adapterهای تلگرام/ایتا/روبیکا (پیادهسازی concrete)
- [ ] اتصال vector store واقعی برای RAG
- [ ] انتشار روی PyPI و GitHub (نیاز به حساب و توکن کاربر)
