# لایه Hybrid — Self-bot بله

کار با **اکانت شخصی** بله، نه توکن ربات. همان چیزی که کلاینت رسمی استفاده
می‌کند، از داخل پایتون.

> ⚠️ **این لایه غیررسمی است.** بله آن را برای استفاده شخص ثالث منتشر نکرده.
> ممکن است بدون اطلاع تغییر کند، و ممکن است اکانتت مسدود شود. با یک شماره
> جداگانه کار کن، نه شماره اصلی. مسئولیت با خودت است.

---

## نصب

```bash
pip install "badking[hybrid]"
```

فقط یک وابستگی اضافه می‌شود: `websockets`. کدک protobuf از صفر نوشته شده،
پس `protobuf` لازم نیست.

---

## ورود

```bash
badking login --phone 09123456789 --session me.session
```

کد SMS را می‌پرسد، session را رمزنگاری‌شده ذخیره می‌کند. بار بعد:

```python
from badking import SelfBot

async with SelfBot(session="me.session") as bot:
    me = await bot.get_me()
    print(me.id, me.title)
```

---

## چه چیزی هست

**۷۹ RPC**، دقیقاً همان‌هایی که کلاینت بله صدا می‌زند. این عدد از سورس
`aiobale` استخراج شده، نه حدس. تطابق یک‌به‌یک:

| سرویس | تعداد | نمونه |
|---|---|---|
| `groups` | ۲۷ | ساخت گروه، ادمین، بن، لینک دعوت، انتقال مالکیت |
| `user` | ۱۶ | مخاطبین، مسدودی، پروفایل، جستجو |
| `messaging` | ۱۲ | ارسال، ویرایش، حذف، فوروارد، سنجاق، تاریخچه |
| `abacus` | ۵ | واکنش، بازدید |
| `auth` | ۵ | ورود، کد، رمز دومرحله‌ای |
| `presence` | ۳ | آنلاین، تایپ |
| `magazine` | ۳ | لایک پست |
| `files` | ۲ | آپلود، دانلود |
| `gift_packet` | ۲ | بسته هدیه |
| `configs` | ۲ | تنظیمات سرور |
| `kifpool` | ۱ | کیف پول |
| `report` | ۱ | گزارش محتوا |

---

## ساختار پیام، همان‌طور که بله می‌خواهد

این جایی است که بیشتر پیاده‌سازی‌ها اشتباه می‌کنند. متن در
`MessageContent` فیلد **۱۵** است، نه ۱. و `SendMessage` فیلد **۶** (`chat`)
را هم لازم دارد:

```
SendMessage {
  1: Peer { 1: type, 2: id, 3: accessHash }
  2: message_id
  3: MessageContent { 15: TextMessage { 1: value } }
  5: reply_to
  6: Chat { 1: type, 2: id }
}
```

کتابخانه این را برایت می‌سازد:

```python
from badking.hybrid import make_text_content, make_chat, make_peer

await bot.call(
    "messaging.SendMessage",
    peer=make_peer("channel", 123, 456),
    message_id=999,
    content=make_text_content("سلام"),
    chat=make_chat("channel", 123),
)
```

---

## API سطح بالا

```python
async with SelfBot(session="me.session") as bot:
    # پیام
    await bot.send_message("@channel", "سلام")
    await bot.send_file("@channel", "report.pdf", caption="گزارش")
    await bot.edit_message("@channel", 123, "متن جدید")
    await bot.delete_messages("@channel", [123, 124])
    await bot.forward_messages("@dest", [123], from_peer="@src")

    # واکنش و بازدید
    await bot.react("@channel", 123, "❤")
    await bot.remove_reaction("@channel", 123, "❤")
    await bot.get_reactions("@channel", 123)
    await bot.get_views("@channel", [123, 124])

    # وضعیت
    await bot.send_typing("@channel")
    await bot.stop_typing("@channel")
    await bot.set_online()
    await bot.mark_read("@channel")

    # سنجاق
    await bot.pin_message("@channel", 123)
    await bot.unpin_message("@channel", 123)
    await bot.get_pinned("@channel")

    # گروه و کانال
    await bot.create_group("گروه من", channel=False)
    await bot.get_group("@group")
    await bot.join_group("https://ble.ir/join/...")
    await bot.leave_group("@group")
    await bot.invite_users("@group", [111, 222])
    await bot.kick_user("@group", 111)
    await bot.get_members("@group")
    await bot.get_invite_link("@group")

    # مخاطبین
    await bot.get_contacts()
    await bot.add_contact("09123456789", "علی")
    await bot.block_user(111)
    await bot.unblock_user(111)

    # پروفایل
    await bot.edit_name("نام جدید")
    await bot.edit_about("بیو جدید")
    await bot.check_username("myusername")

    # تاریخچه
    async for msg in bot.iter_messages("@channel", limit=500):
        print(msg.date, msg.text)

    # گفتگوها
    async for d in bot.iter_dialogs():
        print(d.peer, d.unread, d.last_message)
```

---

## رویدادها

```python
@bot.on(lambda m: m.text == "/ping")
async def ping(msg):
    await msg.reply("pong")

@bot.on_raw
def raw(frame):
    print("فریم خام:", len(frame))

await bot.run_until_disconnected()
```

---

## سه دری که aiobale ندارد

### ۱. `raw_call` — بدون اسکیما

اگر بله متد جدیدی اضافه کند و در جدول ما نباشد:

```python
await bot.raw_call("messaging.NewMethod", {1: peer_bytes, 2: 5})
```

شماره فیلد را می‌دهی، bytes برمی‌گردد. بدون آپدیت کتابخانه.

### ۲. `probe` — کشف متد

```python
result = await bot.probe("messaging.NewMethod")
# {"exists": True}  یا  {"exists": False, "error": "unimplemented"}
```

### ۳. `describe` و `search` — اسکیما از داخل کد

```python
bot.describe("messaging.SendMessage")
# {"name": ..., "service": "bale.messaging.v2.Messaging", "request": {...}, ...}

bot.search("واکنش")
# ["abacus.GetMessageReactionsList", "abacus.GetMessagesReactions", ...]
```

---

## اگر بله پروتکل را عوض کرد

شماره فیلدها در `badking/hybrid/schema.py` است، نه پراکنده در کد. دو راه:

**۱. override بدون دست زدن به کد:**

```bash
export BADKING_RPC_SCHEMA=/path/to/my_schema.json
```

```json
{
  "messaging.SendMessage": {
    "req": { "peer": 1, "message_id": 2, "content": 3, "chat": 6 },
    "resp": { "seq": 1, "date": 2 }
  }
}
```

**۲. از داخل کد:**

```python
from badking.hybrid import registry
registry.load_overrides({"messaging.SendMessage": {"req": {"peer": 1}}})
```

این تفاوت اصلی است: کتابخانه‌ای که شماره فیلد را در صد فایل پخش می‌کند،
با اولین تغییر بله می‌شکند. اینجا یک جدول است.

---

## CLI

```bash
badking rpc                              # همه ۷۹ متد
badking rpc --service groups             # فقط گروه‌ها
badking rpc --search واکنش               # جستجو
badking rpc --describe messaging.SendMessage
badking rpc --json                       # خروجی ماشین‌خوان
```

---

## تست

```bash
pytest tests/test_hybrid.py -q
```

۸۸ تست، همه آفلاین. هیچ اتصالی به سرور بله نمی‌زنند. کدک، session، رجیستری،
قاب‌بندی، و منطق کلاینت با یک transport جعلی تست می‌شوند.

**آنچه تست نشده:** اتصال زنده. برای آن شماره واقعی و کد SMS لازم است.
کد آماده است، ولی تا کسی با شماره خودش لاگین نکند نمی‌توان گفت روی سرور
بله کار می‌کند.

---

## فایل‌ها

| فایل | کار |
|---|---|
| `schema.py` | جدول ۷۹ RPC + ۳۷ تایپ تودرتو + اسکیمای پاسخ |
| `proto.py` | کدک protobuf از صفر، بدون وابستگی |
| `transport.py` | WebSocket، فریم‌بندی، تطبیق id، اتصال مجدد، یادگیری نرخ |
| `auth.py` | جریان شماره + کد SMS |
| `session.py` | ذخیره چند اکانت، رمزنگاری at-rest |
| `rpc.py` | رجیستری، ساخت درخواست، رمزگشایی پاسخ |
| `client.py` | `SelfBot`: ۴۰+ متد سطح بالا |
| `plugin.py` | `HybridPlugin`، پشت `ack_risk=True` |
