# Inline Keyboard در SelfBot

وضعیت: **IMPLEMENTED (source-confirmed) / BLOCKED (live-verified)** — ارسال دکمه از سورس aiobale 0.3.9 تأیید شده، ولی با سرور واقعی بله آزمایش نشده است.

## آنچه میتوانید انجام دهید

ارسال پیام متنی همراه با inline keyboard از اکانت شخصی:

```python
from badking import SelfBot

async with SelfBot(session="badking.session") as bot:
    await bot.send_message(
        "@mychannel",
        "یک گزینه انتخاب کن:",
        reply_markup=[
            [{"text": "بله", "callback_data": "yes"}],
            [
                {"text": "سایت", "url": "https://bale.ai"},
                {"text": "کپی کد", "copy_text": "CODE-123"},
            ],
        ],
    )
```

هر دکمه یک `dict` است. کلیدهای پذیرفتهشده:

| کلید | توضیح |
|---|---|
| `text` | متن دکمه (اجباری، غیرخالی) |
| `callback_data` | payload خروجی دکمه |
| `url` | آدرس وب |
| `copy_text` | متنی که هنگام فشار دکمه کپی میشود |

همچنین نامهای `callbackData` و `copyText` (اسکیما) هم پذیرفته میشوند.

## API

### `SelfBot.send_message(..., reply_markup=None)`

پارامتر `reply_markup` یا لیست ردیف دکمههاست، یا خروجی `make_inline_keyboard()`:

```python
from badking.hybrid import make_inline_keyboard

markup = make_inline_keyboard([[{"text": "تأیید", "callback_data": "ok"}]])
await bot.send_message(peer, "متن", reply_markup=markup)
```

بدون `reply_markup` رفتار دقیقاً مثل قبل است (پیام متن ساده).

### `make_inline_keyboard(rows)`

ساخت ساختار داخلی کیبورد. ورودی نامعتبر (دکمه بدون متن، یا غیر dict) `ValueError` / `TypeError` میدهد.

## محدودیت پروتکلی مهم: callback query وجود ندارد

**هیچ رویداد `on_callback` و هیچ RPCای مانند `answerCallbackQuery` در پروتکل داخلی SelfBot وجود ندارد.** این موضوع با بررسی کامل aiobale 0.3.9 تأیید شد:

- `aiobale/methods/` فاقد هرگونه callback method است.
- `aiobale/types/update.py` فاقد فیلد `callback_query` است.
- `aiobale/dispatcher/router.py` فاقد هندلر callback است.

بنابراین `callback_data` تنها بهعنوان payload خروجی ارسال میشود و نمیتوان فشار دکمه را در SelfBot دریافت کرد. اگر به callback query نیاز دارید، از **Bot API** (`badking.core.Bot`) استفاده کنید که `answer_callback_query` و `on_callback_query` دارد.

## شواهد شماره فیلدها

از سورس رسمی aiobale 0.3.9 (تأییدشده، حدسی نیست):

```
MessageContent.bot_message      = 13   (TemplateMessage)
TemplateMessage.message         = 1    (MessageContent)
TemplateMessage.temp_id         = 2
TemplateMessage.inline_keyboard_markup = 5  (InlineKeyboardMarkup)
InlineKeyboardMarkup.inline_keyboard   = 1  (لیست ردیفها)
Row                             = 1    (لیست دکمهها)
InlineKeyboardButton.text       = 1
InlineKeyboardButton.url        = 2    (wrapper {1: value})
InlineKeyboardButton.callback_data = 3 (wrapper {1: value})
InlineKeyboardButton.copy_text  = 9    (wrapper {1: value})
```

منابع:
- `https://raw.githubusercontent.com/aminmadaniofficial/aiobale/v0.3.9/aiobale/types/inline_keyboard.py`
- `https://raw.githubusercontent.com/aminmadaniofficial/aiobale/v0.3.9/aiobale/types/message_content.py`

این شمارهها **source agreement with aiobale**اند، نه ترافیک تأییدشده سرور بله. تا زمانی که با حساب آزمایشی مجاز تست نشود، وضعیت Live-verified باقی میماند.

## تستها

`tests/test_inline_keyboard.py` — ۱۱ تست آفلاین: شماره فیلدها، نرمالسازی دکمهها، ورودی نامعتبر، ساخت botMessage، کدگذاری wire و اتصال به `send_message`.
