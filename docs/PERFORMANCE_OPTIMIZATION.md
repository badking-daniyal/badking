# Performance Optimization — Serialization

**تاریخ:** 2026-11-20
**روش:** `python benchmarks/bench_serialization.py`
**تنظیمات:** 500 warm-up، 5 دور × 3000 تکرار، ورودی یکسان
**محیط:** Python 3.9.10، Windows، همان ماشین

---

## Bottleneck شناساییشده

`badking/hybrid/proto.py` → `build()`:

هر فیلد با `enc_varint()` / `enc_bytes()` encode میشد. هرکدام:
1. `_tag()` → `write_varint()` → **bytearray + bytes** میساخت
2. `write_varint()` → **bytearray + bytes** دوم میساخت
3. `tag + value` → **bytes سوم**
4. `out += ...` → الحاق

⇒ **۴ تخصیص حافظه به ازای هر فیلد**، حتی برای یک عدد ساده.

---

## بهینهسازی

- `_put_varint(out, value)` اضافه شد: مستقیم داخل همان `bytearray` مینویسد
- `build()` بازنویسی شد: تمام فیلدها مستقیم به بفر نهایی، بدون bytes میانی
- `write_varint()` عمومی حفظ شد (سازگاری API) ولی حالا از `_put_varint` استفاده میکند

**هیچ شماره فیلد، wire type یا ترتیب بایتها تغییر نکرد.**

---

## نتایج قبل / بعد

| معیار | قبل | بعد | بهبود |
|---|---:|---:|---:|
| `build()` median | 0.008039 ms | **0.004838 ms** | **~40٪** |
| `build()` P95 | 0.008302 ms | **0.005477 ms** | ~34٪ |
| `encode_named()` median | 0.022371 ms | **0.015411 ms** | **~31٪** |
| `encode_named()` P95 | 0.025080 ms | **0.016419 ms** | ~35٪ |
| `build()` peak memory | 1.10 KB | 1.11 KB | بدون تغییر |
| `encode_named()` peak memory | 3.23 KB | 3.22 KB | بدون تغییر |

---

## مقایسه با aiobale (ورودی یکسان، همان دوره)

| کتابخانه | median | P95 | P99 | peak memory |
|---|---:|---:|---:|---:|
| BADKING `build()` | **0.004838 ms** | **0.005477 ms** | **0.005477 ms** | **1.11 KB** |
| BADKING `encode_named()` | 0.015411 ms | 0.016419 ms | 0.016419 ms | 3.22 KB |
| aiobale `ProtoBuf.encode()` | 0.016282 ms | 0.017450 ms | 0.017450 ms | 2.25 KB |

**نتیجه صادقانه:**
- BADKING `build()` حدود **۳.۴ برابر سریعتر** از aiobale است
- BADKING `encode_named()` حدود **سریعتر** از aiobale است (۰.۰۱۵۴ در برابر ۰.۰۱۶۳)
- aiobale در مصرف حافظه `encode_named` کمی بهتر است (2.25 در برابر 3.22 KB)

---

## تضمین صحت

`tests/test_serialization_equivalence.py`:

- پیادهسازی مرجع (کد قبل از بهینهسازی) دوباره نوشته شد
- خروجی باینری `build()` و `write_varint()` با **بیش از ۷۰۰ ورودی** (تصادفی + لبهها) مقایسه شد
- **همه بایتها دقیقاً یکسان** — ۵ تست پاس

همچنین `tests/test_protocol_verification.py` (۱۶ تست) تأیید میکند شماره فیلدها با aiobale 0.3.9 مطابقت دارند.

---

## قابل تکرار بودن

```bash
python benchmarks/bench_serialization.py
```

اسکریپت در مخزن است و نتایج خام به صورت JSON چاپ میشوند.
