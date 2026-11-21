# دانلود رسانه در SelfBot — BADKING 0.2.2

قابلیت دانلود فایل از پیامهای بله در لایه SelfBot (API داخلی). مستقل،
جریانی (streaming)، امن و دارای تست آفلاین کامل.

> **هشدار پروتکل**: شماره فیلدها از سورس رسمی aiobale 0.3.9 تأیید شدهاند،
> ولی **هیچ ترافیک واقعی سرور بله در مخزن وجود ندارد**. رفتار سرور (URL برگشتی،
> هدرها، انقضای لینک) Live-verified نیست. تستها全部 Mockاند.

---

## نصب

```bash
pip install "badking[hybrid]"   # httpx وابستگی اصلی است
```

---

## مثال ساده

```python
import asyncio
from badking.hybrid import SelfBot

async def main():
    async with SelfBot(session="me.session") as bot:
        # دانلود با file_id و access_hash
        path = await bot.download_file(
            file_id=123456,
            access_hash=789,
            destination="./downloads",
        )
        print(path)  # ./downloads/file_123456.bin

asyncio.run(main())
```

## مثال پیشرفته: دانلود رسانه یک پیام

```python
import asyncio
from badking.hybrid import SelfBot, DownloadError

async def main():
    async with SelfBot(session="me.session") as bot:
        async for msg in bot.iter_messages("@mychannel", limit=20):
            if msg.media_info() is None:
                continue
            def progress(done, total):
                print(f"{done} بایت دانلود شد")
            try:
                path = await msg.download(
                    destination="./media",
                    base_dir="./media",       # مرز مجاز — جلوگیری از خروج
                    max_size=100 * 1024**2,   # حداکثر 100 MiB
                    on_progress=progress,
                )
                print("ذخیره شد:", path)
            except DownloadError as e:
                print("دانلود نشد:", e, e.hint)

asyncio.run(main())
```

---

## API

### `SelfBot.get_file_url(file_id, access_hash=0) -> dict`

RPC تأییدشده `files.GetNasimFileUrl` را صدا میزند و برمیگرداند:
`{"url", "chunk_size", "timeout", "file_id"}`.

### `SelfBot.download_file(file_id, access_hash, **kwargs) -> Path`

| پارامتر | توضیح |
|---|---|
| `destination` | پوشه یا مسیر فایل (پیشفرض پوشه جاری) |
| `base_dir` | مرز مجاز مسیر؛ خروج از آن `DownloadError` میدهد |
| `filename` | نام دلخواه (sanitize میشود) |
| `overwrite` | پیشفرض `False` → فایل تکراری با پسوند `(1)` ذخیره میشود |
| `max_size` | سقف حجم، پیشفرض 2 GiB |
| `chunk_size` | پیشفرض مقدار پیشنهادی سرور (aiobale: 65536) |
| `timeout` | timeout شبکه (per-operation)، پیشفرض `self.timeout` |
| `total_timeout` | مهلت مطلق کل دانلود به ثانیه، پیشفرض ۶۰۰ — جلوی Slow HTTP Trickle را میگیرد؛ `None` = بدون محدودیت |
| `on_progress(done, total)` | فراخوانی پیشرفت (اختیاری) |

### `Message.media_info() -> dict | None`
اطلاعات `fileId`, `accessHash`, `name`, `size`، یا `None` اگر پیام رسانه ندارد.

### `Message.download(**kwargs) -> Path`
استخراج خودکار شناسه رسانه از پیام و دانلود آن.

---

## امنیت

- **Path Traversal**: تمام نامها sanitize میشوند؛ `..`، `/`، `\` و URL-encoded
  معادلهایشان حذف میشوند. `base_dir` مرز سخت است.
- **Atomic write**: فایل موقت `.part` در همان پوشه → fsync → `os.replace`.
  فایل مقصد تا لحظه replace دستنخورده میماند.
- **پاکسازی**: هر خطا (شبکه، timeout، حجم، دیسک) فایل موقت را حذف میکند.
- **حافظه**: جریان چانکبهچانک نوشته میشود؛ کل فایل در RAM بارگذاری نمیشود.
- **هدرها**: فقط `User-Agent` و `Origin: https://web.bale.ai` — توکن دسترسی
  در GET دانلود فرستاده نمیشود (مطابق aiobale).
- **SSRF**: URL سرور و هر ریدایرکت دوباره اعتبارسنجی میشوند؛ فقط HTTP(S) با
  IP عمومی مجاز است. `follow_redirects=False` + حداکثر ۵ ریدایرکت.
- **Slow HTTP Trickle**: `total_timeout` (پیشفرض ۶۰۰ ثانیه) یک مهلت مطلق
  براساس ساعت دیوار است — برخلاف `timeout` که per-operation است. سروری که هر
  چند ثانیه یک بایت بفرستد، بعد از مهلت متوقف و فایل موقت پاک میشود.
  تست: `tests/test_slow_trickle.py`.

---

## خطاها

تمام خطاها از نوع `badking.hybrid.DownloadError`اند (با `.hint` توضیحی):

- مسیر خارج از مرز، نام نامعتبر، حجم بیش از حد، عدم وجود رسانه،
  خطای RPC، خطای شبکه/timeout، خطای نوشتن دیسک.

---

## شماره فیلدها (منبع: aiobale 0.3.9)

```
GetNasimFileUrl:  file=1  (FileInfo)
FileInfo:         fileId=1, accessHash=2, fileStorageVersion=3
FileURLResponse:  file_urls=1 (repeated)
FileURL:          fileId=1, url=2, timeout=3, chunkSize=7
```

> **تصحیح باگ**: قبل از این مرحله، `NESTED["FileURL"]` در BADKING به اشتباه
> `{url:1, name:2, size:3}` بود. پاسخ سرور خراب دیکود میشد. اکنون مطابق
> سورس رسمی اصلاح شده و تست `test_protocol_fields_media` از آن محافظت میکند.

---

## محدودیتها / BLOCKED

- **Live verification**: بدون حساب آزمایشی مجاز، رفتار واقعی سرور تأیید نشده است.
- **Media Resume**: هیچ پروتکل resumeای در aiobale وجود ندارد (`chunkSize` فقط
  اندازه قطعه است، نه offset). پیادهسازی نشد.
- **Inline Callback** در SelfBot: BLOCKED (RPC مربوطه موجود نیست). ارسال دکمه
  پیادهشده (`docs/SELF_INLINE_KEYBOARD.md`) ولی دریافت فشار دکمه ممکن نیست.
- **DNS Rebinding**: `validate_download_url` IPها را در لحظه اعتبارسنجی چک
  میکند، ولی بین resolve و connect فاصله است. حذف کامل نیاز به IP pinning
  در اتصال httpx دارد — فعلاً **BLOCKED** (بدون تغییر رفتار پروتکل).
- `FileInfo.fileStorageVersion` پیشفرض 1 ارسال نمیشود؛ اگر سرور آنرا الزامی
  کند، نیاز به ترافیک واقعی برای تأیید است.
