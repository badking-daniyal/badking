# BADKING — Master Audit Report

**تاریخ:** 2026-11-20
**دامنه:** کل مخزن، مستندات آنلاین، تستها، وابستگیها، امنیت، معماری
**منبع الزامات:** `D:\AI\edit.txt` (Master Engineering Mission)

---

## 1. وضعیت مخزن

| مورد | مقدار |
|---|---|
| Branch | `main` |
| Commit | `476c24f` |
| Remote | همگام با GitHub (`badking-daniyal/badking`) |
| CI | سبز — Python ۳.۹، ۳.۱۰، ۳.۱۱، ۳.۱۲ |
| Pages deploy | success |
| سایت زنده | `https://docs.badking.ir` — HTTP 200 |
| تستها | ۹۶۳ پاس، ۰ شکست |
| فایلهای محلی تغییریافته | ۰ (پاک) |

---

## 2. ساختار واقعی

```
badking/                    ۳۴ پکیج
├── core/                   Bot, Dispatcher, Router, errors
├── hybrid/                 self-bot: ۷۹ RPC، proto، transport، auth، session
├── storage/                Memory, SQLite, Redis, PostgreSQL
├── media/                  MediaEngine + processing
├── moderation/             Moderator + ChannelMonitor
├── compat/                 Migration Analyzer/Transformer
├── security/               secrets, audit, antispam
├── plugins/ i18n/ jobs/ observability/ testing/ ...
tests/                      ۲۸ فایل تست
examples/                   ۲۸ نمونه
docs/                       bale-api, roadmap, fa/README, en/README
.github/workflows/          ci.yml, pages.yml
```

---

## 3. قابلیت واقعی در برابر مستندشده

تفاوت مهمی که در آودیت پیدا شد:

**نمونهها از APIای استفاده میکردند که وجود نداشت.** ۲۰ نمونه از
`bot.run()`، `@bot.on_message` و `message.reply()` استفاده میکردند، ولی `Bot`
فقط `polling()` و `Dispatcher` جداگانه داشت. تست AST فقط سینتکس را میگرفت،
نه وجود متد.

**اقدام:** به جای اصلاح ۲۰ نمونه، رابط راحت به کتابخانه اضافه شد:
- `Message.reply()` → alias واقعی `answer()`
- `Bot.on_message()` / `on_callback()` → ثبت هندلر در Dispatcher داخلی
- `Bot.run()` → `polling(dispatcher)`
- تست `tests/test_example_api.py` تضمین میکند دوباره پیش نیاید.

سایر متدهای Bot API مفقود (`ban_chat_member`، `unban_chat_member`،
`restrict_chat_member`، `send_media_group`، `get_chat_member_count`) هم اضافه شدند.

---

## 4. وابستگیها و نسخه Python

- `requires-python = ">=3.9"` — واقعاً در CI روی ۴ نسخه تست میشود.
- وابستگیهای اصلی حداقل: `pydantic`, `httpx`, `aiohttp`, `eval_type_backport` (برای ۳.۹)
- Optional extras: `redis`, `postgres`, `mongo`, `ai`, `hybrid`, `all`, `dev`
- مشکل شناختهشده: `Path.write_text(newline=...)` و `Callable[...] | None` در ۳.۹ کار نمیکنند — قبلاً رفع شد.

---

## 5. یافتههای امنیتی

### مثبت
- Sessionها رمزنگاریشده (PBKDF2-HMAC-SHA256 + HMAC integrity)
- توکنها از لاگ پاک میشوند
- Path Traversal در Media Engine مسدود است
- `safe_filename()` و `validate_extension()` پیادهاند
- تنها یک نویسنده در Git history — بدون Perch attribution

### نیاز به اقدام
- **CLI `badking security scan` وجود ندارد** (بخش ۱۵ سند صریحاً خواسته)
- Secret detection خودکار فقط بهصورت توابع پراکنده است، نه scanner یکپارچه

---

## 6. نقاط ضعف و کد تکراری

- `compat/` فقط `__init__.py` دارد ولی کد مهاجرت در همان فایل است — قابل تجزیه به `analyzer.py` / `transformer.py` / `mapping.py` (غیربحرانی).
- `conversation/`, `plugins/`, `methods/` فقط `__init__.py`اند — پیادهسازی در جاهای دیگر است. ساختار پیشنهادی سند «پوشه تکراری ایجاد نکن» میگوید — پس مشکل نیست، ولی مستندسازی محل واقعی لازم است.
- تستها ۱۰ ResourceWarning از event loop بستهنشده دارند — non-critical ولی قابل پاکسازی.

---

## 7. محدودیتهای صادقانه API بله

- اعدادی مثل «۲ پیام/ثانیه» یا «۴۰۹۶ کاراکتر» در مستندات رسمی بله نیستند → پیشفرض قابلتنظیم، نه واقعیت.
- برخی رویدادها (مثل ReactionUpdated) بسته به نوع دسترسی متفاوتاند → framework فقط آنچه واقعاً میآید را Native مینامد.
- API داخلی self-bot غیررسمی است و میشکند → transport جدا و اسکیما قابل override است.
- تست زنده self-bot نیاز به شماره واقعی + SMS دارد → فعلاً BLOCKED.

---

## 8. خلاصه کمبودها (مرتبشده)

1. `docs/COMPETITIVE_ANALYSIS.md` — نیست
2. `badking security scan` — نیست
3. `migration/mappings.json` — نیست
4. مستندات ۳۹ بخشی — فقط ۴ فایل مارکداون
5. Benchmark — نیست
6. Media resume — نیست
7. MySQL/MongoDB storage — نیست (اختیاری)
8. PyPI publish — BLOCKED (حساب کاربر)

---

## 9. برنامه اجرا (مرحلهای)

| Phase | کار | وضعیت |
|---|---|---|
| A | تثبیت + IMPLEMENTATION_STATUS + MASTER_AUDIT | ✅ در حال اتمام |
| B | Security CLI scanner | ⬜ بعدی |
| C | Migration mappings.json | ⬜ |
| D | Competitive Analysis + docs skeleton | ⬜ |
| E | Benchmark | ⬜ |
| F | QA نهایی، CI، push | ⬜ |

**اولویت سند:** Reliability > Correctness > Security > Compatibility > Performance > DX > New Features
