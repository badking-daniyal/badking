# لایه Hybrid — Self-Bot

> **هشدار جدی:** این لایه با API داخلی بله کار می‌کند، نه API رسمی بازو.
> استفاده از آن ممکن است اکانت شخصی‌ات را مسدود کند. با اکانت اصلی وارد نشو.
> این کد آگاهانه و با `ack_risk=True` فعال می‌شود، هرگز خودکار.

---

## چرا این لایه وجود دارد

API رسمی بله (`tapi.bale.ai`) فقط چیزی را می‌دهد که @botfather اجازه داده باشد.
کارهایی که با توکن رسمی **از هیچ کتابخانه‌ای** ممکن نیست:

- خواندن تاریخچه پیام‌های قدیمی
- ارسال از اکانت شخصی (نه ربات)
- دیدن وضعیت آنلاین، «در حال تایپ»، واکنش‌ها
- عضویت و مدیریت گروه/کانال بدون ادمین بودن ربات
- کیف پول و انتقال پول
- هر چیزی که اپ موبایل بله می‌کند ولی ربات نمی‌تواند

این لایه همان دسترسی را می‌دهد.

## چه چیزی از aiobale بهتر است

| موضوع | aiobale | BADKING Hybrid |
|---|---|---|
| شماره فیلدهای پروتکل | داخل کد پراکنده | یک جدول JSON قابل override |
| اگر بله پروتکل را عوض کند | کتابخانه می‌شکند | `BADKING_RPC_SCHEMA` را عوض کن |
| رمزگشایی پیام تودرتو | حدسی | اسکیما-محور (متن خراب نمی‌شود) |
| ذخیره session | فایل ساده | رمزنگاری‌شده + چند اکانت |
| یادگیری محدودیت نرخ | ثابت | از `retry_after` سرور یاد می‌گیرد |
| اتصال مجدد | پایه | backoff نمایی + صف درخواست‌ها |
| تست | نامشخص | ۷۴ تست آفلاین |
| RPC های آماده | ۸۰+ | ۵۸ با اسکیما + هر RPC دلخواه |

نکته مهم: **شماره فیلدها در هیچ‌کدام «رسمی» نیست.** تفاوت این است که
اینجا اگر اشتباه بود، در یک فایل عوضش می‌کنی، نه در ۵۰ فایل.

---

## نصب

```bash
pip install "badking[hybrid]"
```

وابستگی‌ها: `websockets` و `protobuf`.

---

## شروع سریع

```python
import asyncio
from badking.hybrid import SelfBot

async def main():
    async with SelfBot(session="me.session") as bot:
        me = await bot.get_me()
        print("وارد شدم به:", me)

        # ارسال از اکانت شخصی
        await bot.send_message("@my_channel", "سلام از BADKING")

        # خواندن تاریخچه
        async for msg in bot.iter_messages("@my_channel", limit=100):
            print(msg.date, msg.text)

asyncio.run(main())
```

بار اول که `me.session` وجود ندارد، باید شماره بدهی:

```python
async with SelfBot(session="me.session", phone="09123456789") as bot:
    ...
```

کد SMS را می‌پرسد و session را ذخیره می‌کند. دفعه بعد بدون کد وصل می‌شوی.

---

## ورود از ترمینال

```bash
badking login --phone 09123456789 --session me.session
```

یا با رمز برای رمزنگاری فایل session:

```bash
badking login --phone 09123456789 --session me.session --password mysecret
```

بعدش هر بار:

```bash
export BADKING_SESSION_KEY=mysecret
```

---

## چند اکانت

```python
from badking.hybrid import SessionStore

store = SessionStore("accounts.session", password="secret")
print(store.list_accounts())
# [{'key': 'user:123', 'phone': '98912...', 'name': 'دانیال', 'valid': True}]

session = store.get("user:123")
bot = SelfBot(session=session)
```

---

## ارسال همه نوع پیام

```python
# متن
await bot.send_message("@channel", "سلام")

# پاسخ به پیام
await bot.send_message("@channel", "پاسخ", reply_to=12345)

# بی‌صدا
await bot.send_message("@channel", "بی‌صدا", silent=True)

# ویرایش
await bot.edit_message("@channel", 12345, "متن جدید")

# حذف
await bot.delete_messages("@channel", [12345], revoke=True)

# فوروارد
await bot.forward_messages("@dest", [12345], from_peer="@source")

# واکنش
await bot.react("@channel", 12345, "❤")

# تایپ کردن
await bot.send_typing("@channel")

# خوانده‌شده
await bot.mark_read("@channel")
```

---

## رویدادها (event handlers)

```python
from badking.hybrid import SelfBot

bot = SelfBot(session="me.session")

@bot.on(lambda m: m.text == "/ping")
async def ping(msg):
    await msg.reply("pong")

@bot.on(lambda m: "سلام" in m.text)
async def salam(msg):
    await msg.react("👋")

@bot.on()  # همه پیام‌ها
async def log(msg):
    print(f"{msg.chat_id}: {msg.text}")

async def main():
    async with bot:
        await bot.run_until_disconnected()
```

رویداد خام (هر update، حتی آن‌هایی که تفسیر نشده‌اند):

```python
@bot.on_raw
def raw(frame: bytes):
    print("update خام:", len(frame), "بایت")
```

---

## هر RPC، حتی ناشناخته‌ها

لایه ۲ دسترسی خام است. هر متدی که در رجیستری باشد:

```python
resp = await bot.call("messaging.LoadHistory",
                      peer={"type": 4, "id": 123, "accessHash": 456},
                      date=-1, loadMode=2, limit=20)
```

دیدن همه متدها:

```python
from badking.hybrid import registry

for name in registry.names():
    print(name)

# گروه‌بندی بر اساس سرویس
for service, methods in registry.by_service().items():
    print(service, len(methods))
```

اضافه کردن متد خودت:

```python
from badking.hybrid import RpcSpec, registry

registry.register(RpcSpec(
    name="custom",
    service="custom",
    method="MyMethod",
    req={"foo": 1, "bar": 2},
    resp={"result": 1},
))

resp = await bot.call("custom.MyMethod", foo="x", bar=5)
```

---

## اگر بله پروتکل را عوض کرد

این مهم‌ترین بخش است. شماره فیلدها را در یک فایل JSON بنویس:

```json
{
  "messaging.SendMessage": {
    "req": { "peer": 1, "rid": 2, "message": 3 },
    "resp": { "rid": 1, "date": 2 }
  }
}
```

بعد:

```bash
export BADKING_RPC_SCHEMA=/path/to/schema.json
```

یا در کد:

```python
from badking.hybrid import registry
registry.load_schema_file("schema.json")
```

**بدون آپدیت کتابخانه.** این تفاوت اصلی با هر پیاده‌سازی دیگری است.

---

## محدودیت نرخ

سرور بله `retry_after` برمی‌گرداند. BADKING از آن یاد می‌گیرد:

```python
bot = SelfBot(session="me.session")
await bot.connect()

print(bot._transport.rate.min_interval)   # فاصله‌ای که یاد گرفته
print(bot._transport.rate.observed_retry_after)  # تاریخچه
```

هر بار که محدود می‌شوی، فاصله پایه خودش بالا می‌رود. لازم نیست دستی تنظیم کنی.

---

## آمار اتصال

```python
print(bot.stats())
# {'connected': True, 'sent': 42, 'received': 118, 'reconnects': 0, 'errors': 0}
```

---

## ریسک‌ها — بدون تعارف

| ریسک | واقعیت |
|---|---|
| مسدود شدن اکانت | واقعی. بله می‌تواند اکانت را ببندد. |
| شکستن پروتکل | واقعی. هر چند ماه احتمالاً. |
| تست خودکار | غیرممکن بدون شماره واقعی. |
| پشتیبانی | هیچ. غیررسمی است. |
| قوانین بله | ممکن است نقض شود. مسئولیتش با توست. |

**توصیه:** با یک شماره جداگانه و اکانت تست کار کن. اکانت اصلی‌ات را وصل نکن.

---

## معماری

```
badking/hybrid/
├── session.py     ذخیره امن اکانت‌ها (چند اکانت، رمزنگاری at-rest)
├── proto.py       کدک protobuf از صفر، بدون .proto
├── transport.py   WebSocket، تطبیق درخواست/پاسخ، اتصال مجدد، یادگیری نرخ
├── rpc.py         رجیستری ۵۸ متد با شماره فیلد قابل override
├── auth.py        جریان شماره + کد SMS
├── client.py      API سطح‌بالا (SelfBot)
└── plugin.py      اتصال به Dispatcher، خاموش پیش‌فرض
```

هر ماژول جدا تست می‌شود. `proto.py` هیچ وابستگی خارجی ندارد.

---

## تست

```bash
pytest tests/test_hybrid.py -v
```

۷۴ تست، همه آفلاین. هیچ اتصال شبکه‌ای به بله نمی‌زنند.
