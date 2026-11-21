# قفل Between-Process Session Storage

## مشکلی که رفع شد

پیشتر `SessionStore.put()` یک Read-Modify-Write بود که فقط توسط
`threading.RLock` محافظت میشد. دو process مستقل میتوانستند همزمان فایل
session را بخوانند، هرکدام کپی خود را بنویسد و نوشته دیگری را پاک کند.

**بازتولید واقعی (قبل از اصلاح):** ۲ process × ۵ نوشتن = ۱۰ حساب مورد انتظار،
اما تنها ۵ حساب باقی ماند (Lost Update).

## معماری نهایی

دو لایه قفل، همیشه به همین ترتیب:

1. **`threading.RLock` per-path** — هماهنگی threadهای همان process و جلوگیری
   از deadlock ناشی از باز شدن fd جداگانه توسط دو thread.
2. **قفل فایل سیستمی** (`badking/hybrid/session_lock.py`) — هماهنگی processهای
   مستقل:
   - Windows: `msvcrt.locking`
   - POSIX: `fcntl.flock`
   - هر دو stdlibاند؛ وابستگی جدیدی اضافه نشد.

### چرا فایل قفل جداگانه؟

فایل session توسط `os.replace` جایگزین میشود. اگر قفل روی خود فایل session
میبود، هر نوشتن قفل processهای دیگر را بیاثر میکرد. قفل روی
`<session>.lock` میماند که هرگز جایگزین یا حذف نمیشود.

### Crash safety

قفل به file descriptor متصل است؛ اگر process بدون آزادسازی بمیرد،
سیستمعامل آنرا خودکار آزاد میکند. تست
`test_crash_while_holding_lock_does_not_block_others` این را با process واقعی
و `os._exit(7)` هنگام نگه داشتن قفل اثبات میکند.

### Timeout و Starvation

پیشفرض: `BADKING_SESSION_LOCK_TIMEOUT=120` ثانیه. الگوریتم انتظار شامل
backoff با jitter تصادفی است تا processها همزمان تلاش نکنند (starvation).
مقادیر نامعتبر (`abc`، منفی، `nan`، `inf`) هنگام خواندن از محیط به `120`
پیشفرض برمیگردند و باعث کرش هنگام import نمیشوند.

### Reentrancy چند-path

قفلها بهازای key در thread ذخیره میشوند (دیکشنری، نه تک مقدار). بنابراین
الگوی «قفل A → قفل B → دوباره قفل A» دچار خود-deadlock نمیشود. نسخه قبلی
فقط آخرین قفل thread را نگه میداشت و بازگشت به A را contention میپنداشت.

## امنیت Session حفظ شد

- AES-256-GCM (BKS3) و PBKDF2-SHA256 (600k) بدون تغییر.
- هدر و AAD محافظت میشوند؛ downgrade و دستکاری رد میشود.
- Migration و Rollback تحت همان قفل قرار گرفتند.
- Atomic write، مجوز 0600 و فایل موقت منحصربهفرد بدون تغییر.
- **کش کلید مشتقشده** بهازای `(HMAC(password), salt, rounds)` فقط در حافظه
  process: PBKDF2 گران (۰.۶s) دیگر در هر RMW دوباره محاسبه نمیشود. password
  خام در کلید کش نگه داشته نمیشود (شناسه یکطرفه HMAC-SHA256 با کلید تصادفی
  سطح-ماژول استفاده میشود). هیچ کلید یا رمزی روی دیسک نوشته نمیشود.

## API اتمیک جدید: `update()`

`get()` سپس `put()` **اتمیک نیست** — قفل بین آنها آزاد میشود و در محیط
چندپردازشی Lost Update میدهد. متد جدید:

```python
store.update("user:123", lambda s: s)
```

خواندن، اعمال تغییر و نوشتن را تحت یک قفل واحد انجام میدهد. تست
`test_concurrent_read_modify_write_no_lost_increment` با ۵ process × ۴ بار
افزایش، شمارنده ۲۰ را اثبات میکند.

رفتار تعریفشده:
- نبودن کلید → `None` (بدون نوشتن).
- updater باید `Session` برگرداند؛ بازگشت `None` یا نوع نامعتبر →
  `SessionError` و فایل سالم باقی میماند (تست
  `test_update_missing_key_and_invalid_return`).
- استثنای داخل updater → قفل آزاد میشود و فایل تغییر نمیکند (تست
  `test_data_preserved_after_failed_write`).

## عملکرد

| معیار | قبل | بعد |
|---|---|---|
| نوشتن رمزدار تکی | ~۱.۳۸s | ~۰.۴۷–۰.۶۲s (کش کلید) |
| Lost Update (۲ process × ۵) | ۵/۱۰ باقی | ۱۰/۱۰ باقی |
| استرس ۸ process × ۵ نوشتن | ناموفق | ۴۰/۴۰ باقی |

## وضعیت

- `VERIFIED`: عدم Lost Update با processهای واقعی (Windows spawn)، ۱۱ تست.
- `VERIFIED`: Crash holder، Lock timeout، ترکیب thread+process، migration همزمان.
- `MOCK-VERIFIED`: رفتار POSIX (`fcntl.flock`) — منطق یکسان است ولی تست واقعی
  فقط روی Windows اجرا شد؛ CI Ubuntu آنرا پوشش میدهد.
- `NOT VERIFIED`: رقابت شدیدتر از ۱۰ process همزمان (تستشده: ۱۰ process).
