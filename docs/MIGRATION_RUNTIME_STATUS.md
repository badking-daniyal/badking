# Migration Runtime Status — بررسی دقیق balethon

**تاریخ:** 2026-11-20
**پروژه نمونه:** `backup.zip` → `bot.py` (۱۲۴۱ خط) + `utils/*` + `balecore` (۷۲ فایل)

---

## نتیجه صریح

**پروژه نمونه قابلیت مهاجرت کامل ندارد. فقط Import آن موفق شده است.**

ادعای قبلی («4/4 فایل معتبر، ۱۰۰٪») درست بود ولی **گمراهکننده** بود:
منظور «syntax + import» بود، نه «رفتار کامل ربات». این سند آنرا تصحیح میکند.

---

## یافتهها

### ۱) Migration Center فقط aiobale را پوشش میدهد

| ورودی | تبدیل | نتیجه |
|---|---|---|
| `from aiobale import Client, Dispatcher` | ✅ | به BADKING تبدیل شد |
| `from aiobale.enums...` | ✅ | تبدیل شد |
| `from aiobale.methods.base import BaleMethod` | ✅ | `BaleMethod` compat اضافه شد |
| `from balecore import Bot` | ❌ | **تبدیل نشد** (خارج از محدوده aiobale) |
| `@bot.Message(commands=["start"])` | ❌ | **تبدیل نشد** |
| `@bot.CallbackQuery(...)` | ❌ | **تبدیل نشد** |

### ۲) دکوراتورهای balethon واقعاً چهاند

از سورس واقعی `balecore/bots/bot.py` (استخراجشده از بکاپ):

```python
def Message(self, *, commands=None, pattern=None,
            content_types=None, state=None, custom_filter=None): ...
def CallbackQuery(self, __filter=None): ...
```

اینها دکوراتورهای ثبت handlerاند. BADKING self-bot فقط `on_raw()` دارد —
**معادل مستقیمی برای `Message`/`CallbackQuery` وجود ندارد.**

### ۳) آزمایش واقعی

| مرحله | نتیجه |
|---|---|
| استخراج کامل وابستگیها | ✅ |
| اجرای Migration (۶ تغییر) | ✅ |
| Syntax | ✅ |
| Import با دکوراتورها خنثی | ✅ `IMPORT_OK` |
| Import بدون خنثی کردن | ❌ `AttributeError: 'Bot' object has no attribute 'Message'` |
| اجرای ربات و پاسخ به `/start` | ❌ **غیرممکن** — دکوراتورها ثبت نشدهاند |

---

## چرا دکوراتورها را حذف نکردم

دستور صریح تو: «هیچ Decorator یا منطق برنامه را بدون دلیل حذف نکن.»
من آنها را در کد مبدل **نگه داشتم** و فقط در آزمایش تشخیصی (یک فایل موقتی
که پاک شد) خنثی کردم تا ببینم بقیه ماژولها سالماند. نتیجه: سالماند.

---

## وضعیت نهایی

| معیار | وضعیت |
|---|---|
| Import ماژولهای تبدیلشده | ✅ TESTED |
| Syntax تمام فایلها | ✅ TESTED |
| تبدیل importهای aiobale | ✅ TESTED |
| تبدیل دکوراتورهای balethon | ❌ NOT_IMPLEMENTED |
| اجرای رفتار ربات (پاسخ به پیام) | ❌ NOT_IMPLEMENTED / BLOCKED |
| اجرای زنده با توKEN | ⛔ BLOCKED (توKEN بکاپ افشاشده، rotate لازم است) |

---

## پیشنهاد (بدون اجرا، چون «قابلیت جدید غیرضروری» ممنوع است)

اگر خواستی مهاجرت balethon هم پوشش داده شود، یک ماژول `compat/balethon.py`
لازم است که دکوراتورها را به `on_raw()` + filter تبدیل کند. **تا تأیید تو اضافه نمیشود.**
