# Protocol Verification — شماره فیلدها با منبع معتبر

**تاریخ:** 2026-11-20
**منبع معتبر:** سورس کامل `aiobale_py 0.3.9` (۵۷۴ فایل، استخراجشده از `backup.zip`)
**روش:** مقایسه AST — `pydantic Field(alias="N")` در aiobale در برابر `METHODS` در `badking/hybrid/schema.py`

---

## نتیجه اصلی

| معیار | نتیجه |
|---|---|
| متدهای aiobale با alias شماره فیلد | ۷۲ |
| متدهای BADKING در schema | ۷۸ |
| متدهای تطبیقشده (همه فیلدها یکسان) | **۷۲ / ۷۲ = ۱۰۰٪** |
| متد گم‌شده در BADKING | **۰** |
| عدم تطابق شماره فیلد | **۰** |
| متد اضافی BADKING | ۶ (متدهای بدون alias در aiobale) |

**ادعای قبلی («شماره فیلدها از aiobale استخراج شده») اکنون تأییدشده است** —
دیگر فقط ادعای متنی نیست.

---

## نمونههای تأییدشده

| متد | فیلد | aiobale 0.3.9 | BADKING |
|---|---|---:|---:|
| `SendMessage` | peer | 1 | 1 |
| `SendMessage` | content | 3 | 3 |
| `SendMessage` | chat | 6 | 6 |
| `StartPhoneAuth` | phone_number | 1 | 1 |
| `StartPhoneAuth` | send_code_type | 9 | 9 |
| `ValidateCode` | code | 2 | 2 |
| `GetGroupPreview` | token | 1 | 1 |
| `LoadHistory` | load_mode | 4 | 4 |
| `LoadHistory` | limit | 5 | 5 |

---

## نکته مهم درباره `auth.py`

`badking/hybrid/auth.py` جدول فیلد جداگانه دارد (`F_CODE=3`) در حالی که
سورس معتبر aiobale میگوید `ValidateCode.code = 2`. این یک **ناسازگاری واقعی**
است که در ممیزی Self Client پیدا شد.

- `schema.py` ✅ با aiobale مطابقت دارد (تأییدشد)
- `auth.py` ❌ جدول قدیمی/اشتباه دارد — **BLOCKED** تا مشخص شود کدام مسیر
  در عمل توسط سرور استفاده میشود (نیاز به ترافیک واقعی)

تست `test_protocol_verification.py` فقط `schema.py` را میسنجد، نه `auth.py`.

---

## Serialization / Deserialization

تستهای آفلاین (`tests/test_protocol_verification.py`):

- varint roundtrip (مثبت و منفی)
- nested message roundtrip
- حفظ فیلد ناشناخته
- ساخت payload واقعی `SendMessage` با شماره فیلدهای تأییدشده

همه پاس میشوند (۱۶ تست).

---

## BLOCKED — بدون ترافیک واقعی قابل تأیید نیست

| مورد | دلیل |
|---|---|
| WebSocket framing (length-prefixed در برابر raw) | حدس طراحی، بدون capture |
| `req_id` در فیلد 1 | قرارداد حدسی transport |
| نام متد روی wire | پروتکل ظاهراً نام نمifrستد |
| پاسخهای واقعی سرور | نیاز به حساب آزمایشی |
| صحت `auth.py` جدول قدیمی | نیاز به ترافیک ورود واقعی |

---

## حقوق و attribution

 fixture سورس aiobale در `tests/fixtures/aiobale_methods/` با مجوز MIT و
کپیRIGHT اصلی ذخیره شد. هیچ کدی از آن در runtime BADKING استفاده نمیشود —
فقط توسط تستها پارس میشود.
