# Migration Center — اعتبارسنجی روی پروژه واقعی

**تاریخ:** 2026-11-20
**پروژه نمونه:** `bot.py` (۱۲۴۱ خط) + `utils/database.py` + `utils/menus.py` + `utils/is_join.py`
**منبع:** `D:\AI\backup.zip` — پروژه واقعی مبتنی بر aiobale + balethon
**ابزار:** `badking.compat.analyze` + `badking.compat.migrate_source`

---

## نتایج واقعی

| فایل | خطوط | تغییرات | Unsupported | Syntax OK | Import OK |
|---|---:|---:|---:|:---:|:---:|
| `bot.py` | ۱۲۴۱ | ۶ | ۰ | ✅ | ✅ |
| `database.py` | ۲۹۴ | ۰ | ۰ | ✅ | ✅ |
| `menus.py` | ۶۸ | ۰ | ۰ | ✅ | ✅ |
| `is_join.py` | ۲۶ | ۰ | ۰ | ✅ | ✅ |

**درصد موفقیت (معیار قابل اندازهگیری):**
- Syntax معتبر: **۴/۴ = ۱۰۰٪**
- تمام importهای badking وجود دارند: **۴/۴ = ۱۰۰٪**
- تغییرات اعمالشده: ۶ مورد در `bot.py` (تمام importها)

---

## Importهای تبدیلشده

| قبل | بعد |
|---|---|
| `from aiobale import Client, Dispatcher` | `from badking import Bot, Dispatcher` |
| `from aiobale.enums.send_code import SendCodeType` | `from badking import SendCodeType` |
| `from aiobale.enums.auth_errors import AuthErrors` | `from badking import AuthErrors` |
| `from aiobale.enums.chat_type import ChatType` | `from badking import ChatType` |
| `from aiobale.types import Message` | `from badking import Message` |
| `from aiobale.methods.base import BaleMethod` | `from badking import BaleMethod` |

---

## مشکلات کشفشده و رفعشده

### ۱. `BaleMethod` وجود نداشت
Migration کدی تولید میکرد که `from badking import BaleMethod` میزد ولی این کلاس نبود.
پروژه واقعی از آن برای تعریف RPC سفارشی (`SendInlineCallback`) استفاده میکند.

**رفع:** `badking.compat.BaleMethod` اضافه شد — پل سادهای که اسکیمای کلاس
را نگه میدارد و از طریق `raw_call` اجرا میکند. هیچ RPC تأییدنشانهای اضافه نشد.

### ۲. اسکریپت اعتبارسنجی اشتباه میگرفت
در اولین اجرا، `missing_imports` همه نامها را نشان میداد در حالی که وجود داشتند.
علت: `import badking` داخل تابع و scope اشتباه در اسکریپت آزمایشی بود، نه Migration Center.

**رفع:** اعتبارسنجی با import در سطح ماژول تکرار شد → ۴/۴ import معتبر.

---

## Backup و Rollback

| آزمون | نتیجه |
|---|---|
| Backup بایت دقیق از `backup.zip` | ✅ ۴/۴ فایل MATCH (SHA256) |
| Rollback به محل موقت | ✅ ۴/۴ فایل به حالت اصلی برگشت |

نکته: در اولین تلاش backup با `write_text` نوشته شد و hashها DIFF دادند —
علت تفاوت line-ending/BOM بود، نه نقص Migration. با `write_bytes` (بایت دقیق)
تکرار شد و MATCH شد.

---

## محدودیتهای صادقانه

- **اجرای کامل ربات مهاجرت یافته BLOCKED است.** پروژه نمونه به توکن ربات،
  aiobale، balethon، دیتابیس SQLite و سرور بله نیاز دارد. فقط syntax و import
 ها آزمایش شدند، نه رفتار runtime.
- `BaleMethod.call()` از `raw_call` استفاده میکند ولی صحت شماره فیلدهای
  متد سفارشی (`SendInlineCallback`) بدون ترافیک واقعی **BLOCKED** است.
- درصد موفقیت بالا (۱۰۰٪) مربوط به **معیارهای قابل اندازهگیری آفلاین**
  (syntax + import) است، نه «مهاجرت کامل عملیاتی». ادعای مهاجرت کامل تا زمانی
  که ربات تبدیلشده روی سرور واقعی اجرا نشود، نمیشود.

---

## نتیجه

Migration Center روی یک پروژه واقعی aiobale کار میکند: تمام importها را درست
تبدیل میکند، syntax حفظ میشود، backup/rollback سالم است. یک نقص واقعی
(`BaleMethod`) پیدا و رفع شد. موارد نیازمند حساب واقعی صریحاً BLOCKEDاند.
