# Competitive Benchmark — BADKING در برابر aiobale

**تاریخ:** 2026-11-20
**محیط:** Python 3.9.10، Windows، همان ماشین، همان subprocess تنظیمات
**نسخهها:** BADKING 0.2.2 · aiobale 0.3.9 (از بکاپ)
**روش:** ۵ اجرای جداگانه برای import، ۲۰۰ تکرار برای serialization

---

## نتایج خام

### Startup / Import Time

| کتابخانه | avg | P50 | min |
|---|---:|---:|---:|
| BADKING | **۱۲۰۲ ms** | ۱۱۸۹ ms | ۱۱۸۰ ms |
| aiobale | ۳۰۳۹ ms | ۲۹۷۶ ms | ۲۹۵۰ ms |

**نسبت:** BADKING حدود **۲.۵ برابر سریعتر** در import.

### Serialization (handshake payload واقعی)

| کتابخانه | avg | P50 | P95 |
|---|---:|---:|---:|
| aiobale (blackboxprotobuf) | **۰.۰۱۳۷ ms** | ۰.۰۱۱۷ ms | ۰.۰۲۰۸ ms |
| BADKING (codec دستساز) | ۰.۰۵۷۵ ms | ۰.۰۵۲۷ ms | ۰.۰۷۷۱ ms |

**صادقانه:** aiobale در serialization پیام کوچک **حدود ۴ برابر سریعتر** است.
BADKING در این معیار برتر نیست. دلیل: blackboxprotobuf یک کتابخانه بهینهشده
است، در حالی که کدک ما عمومی و schema-driven است.

### Memory (BADKING، ۱۰۰ serialization)

| شاخص | مقدار |
|---|---:|
| current | ۱۸۰۹۸ KB |
| peak | ۱۸۵۴۰ KB |

---

## معیارهای اندازهگیری نشده (BLOCKED)

| معیار | دلیل |
|---|---|
| Message Processing Latency | نیاز به سرور واقعی |
| Concurrent Processing | نیاز به بار واقعی |
| Connection Stability | نیاز به اتصال زنده |
| CPU Usage | ابزار اندازهگیری در محیط آزمایشی موجود نبود |
| P99 serialization | تعداد نمونه کافی برای P99 پایدار نبود |

---

## نتیجه صادقانه

BADKING **در startup سریعتر** است ولی **در serialization کوچک کندتر** از
aiobale. ادعای «برتری فنی مطلق» تأییدنشده است.

این همان چیزی است که سند مأموریت خواسته: «هیچ ادعای سریعتر بودن بدون
Benchmark معتبر منتشر نکن.» ما Benchmark داریم، پس فقط همان چیزی را که
اندازهگیریم میگوییم.

---

## تکرار آزمایش

اسکریپت benchmark موقتی بود و نتایج آن در این فایل ثبت شده است. برای تکرار،
همان شرایط (subprocess جدا، ۵ بار import، ۲۰۰ بار serialization) را رعایت کن.
