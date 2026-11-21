# خلاصه مستندات رسمی بله (Bale Bot API)

منبع اصلی: https://docs.bale.ai/ — تاریخ بررسی: 2026-11-18

## آدرس و شکل درخواست
- Endpoint: `https://tapi.bale.ai/bot<token>/METHOD_NAME`
- متدهای HTTP: GET و POST
- پارامترها: query string، form-urlencoded، JSON، یا multipart
- پاسخ: JSON با `ok` (true/false)، `result`، `error_code`، `parameters`
- کدگذاری: UTF-8

## نگهداری آپدیتها
- بله **۲۰۰۰ پیام آخر را به مدت ۲۴ ساعت** نگه میدارد.
- بنابراین ربات باید offset خودش را ذخیره کند؛ BADKING این کار را در Update Recovery انجام میدهد.

## وب هوک
- فقط پورتهای **443 و 88** مجازاند.

## محدودیت نرخ
- در API معمولی، نرخ **تعاملی** است (ظرفیت بر اساس میزان تعامل کاربران در چت شخصی).
- اعداد دقیق (2/msgs، 20/burst، 120/min، 4096 کاراکتر، حذف 48 ساعته) در مستندات رسمی نیامدهاند و در BADKING پیشفرض قابلتنظیماند و از `retry_after` سرور یادگیری میکنند.

## API کسبوکاری
- مسیر جداگانه `business` در base URL، سهمیه نرخ مستقل.
- فقط چت شخصی؛ ارسال فایل فقط با `file_id`.
- متدها: `getMe`، `sendMessage`، `forwardMessage`، `sendPhoto`، `sendVideo`، `sendAudio`، `sendDocument`.

## اندازه فایلها
- ارسال با URL: حداکثر 5MB عکس / 20MB سایر.
- ارسال با multipart: حداکثر 10MB عکس / 50MB سایر.
- `file_id` مخصوص هر بازو است و قابل انتقال به بازوی دیگری نیست.

## پرداخت و سفیر
- متدهای `askReview`، `inquireTransaction`، `PreCheckoutQuery` وجود دارند.
- `answerCallbackQuery` حتماً باید فراخوانی شود وگرنه دکمه در حالت انتظار میماند.
- `ForumTopic`: فیلدهای `icon_color` و `icon_custom_emoji_id` برگردانده نمیشوند.

## آپلود فایل (multipart)

مستندات رسمی میگوید: `multipart/form-data` برای آپلود فایل، و `application/json`
برای بقیه موارد. BADKING این را خودکار انجام میدهد:

```python
from badking import Bot

bot = Bot("123456:ABC...")
# مسیر فایل محلی → درخواست multipart/form-data
await bot.send_photo(chat_id, "photo.jpg", caption="توضیح")
await bot.send_document(chat_id, "report.pdf")
# file_id یا URL → درخواست application/json (بدون تغییر رفتار)
await bot.send_photo(chat_id, "AgACAgIAAxkBAAI")
```

- تشخیص براساس «وجود فایل روی دیسک» است؛ file_id و URL دستنخورده میمانند.
- در حالت multipart، پارامترهای ساختاریافته (مثل `reply_markup`) بهصورت
  JSON-string ارسال میشوند — چون form field فقط رشته میپذیرد.
- سقف‌های رسمی: ۱۰MB برای عکس و ۵۰MB برای سند.
- تست: `tests/test_bot_multipart_upload.py`.

## مینیاپ
- شی `window.Bale.WebApp`، ساختار `WebAppInitData`.
- امضای HMAC-SHA256: ابتدا `secret = HMAC_SHA256(key="WebAppData", msg=bot_token)`، سپس امضای `data_check_string` (فیلدها الفبایی مرتب و با `\n` متصل) با `secret`.
- `requestContact` نباید مبنای احراز هویت باشد.
- متن دکمه در اندروید حداکثر 20 کاراکتر.

## سرویس سفیر
- REST با Api Access Key؛ ارسال به شماره، پیام رمزدار، OTP، دکمههای `url`/`web_app`/`copy_text`، قالب پیام با تأیید پشتیبانی، `request_id` برای idempotency.

## قالببندی
- Markdown اصلاحشده بله: `*برجسته*` (نه `**`)، `_کج_` (نه `__`)، `[متن](لینک)`، بلوک کد ```.
- الگوهای `uid:` و `send:`.
