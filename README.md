# BADKING

**فریمورک همه کاره، async و AI-Native برای ساخت ربات‌های [بله (Bale)](https://www.bale.ai/).**

سوپرست aiobale — هر چیزی که aiobale دارد، به‌علاوه چیزهایی که ندارد.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-98%20passed-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-docs.badking.ir-orange)](https://docs.badking.ir)

> از کسی که کد بلد نیست تا یک مهندس حرفه‌ای: سه لایه دسترسی، بدون محدودیت، و هر چیزی قابل ساخت.

---

## چرا BADKING؟

**بدون محدودیت.** هیچ کاری نیست که کتابخانه جلوی تو بگیرد. هر متدی که API بله دارد، در دسترس است — با تایپ‌گذاری کامل، یا با JSON خام.

**سه لایه، یک کتابخانه.** یک نفر بدون کد ربات می‌سازد، یک برنامه‌نویس FSM و AI می‌خواهد، یک مهندس به RPC خام نیاز دارد. هر سه در BADKING هستند و لایه پایین‌تر همیشه باز است.

**AI از روز اول.** دستیار با tool calling، RAG روی فایل‌های خودت، حافظه per-user. نه به‌عنوان افزونه، بلکه بخشی از هسته.

**صادق.** هر جا حدسی زده‌ایم، گفته‌ایم. هر جا API بله چیزی نمی‌دهد، ادعا نکرده‌ایم.

---

## نصب

```bash
# از PyPI
pip install badking

# یا با uv (سریع‌تر)
uv pip install badking

# یا آخرین نسخه توسعه
pip install git+https://github.com/badking-daniyal/badking.git
```

نیازمندی: Python 3.9 یا بالاتر.

---

## شروع در ۵ دقیقه

```python
import asyncio
from badking import Bot, Dispatcher, F

bot = Bot("123456789:TOKEN_FROM_BOTFATHER")
dp = Dispatcher()

@dp.message(F.text == "/start")
async def start(message, bot):
    await bot.send_message(message.chat.id, "خوش آمدی! 🚀")

@dp.message(F.text)
async def echo(message, bot):
    await bot.send_message(message.chat.id, f"شما گفتید: {message.text}")

asyncio.run(bot.polling(dp))
```

توکن را از [@botfather](https://ble.ir/botfather) در بله بگیر. همین. بدون لاگین شماره، بدون session file.

**بدون توکن هم می‌شود تست کرد:**

```bash
python examples/echo_bot.py --mock
```

---

## نمونه‌های واقعی

### ۱. ویزارد چندمرحله‌ای (Conversation)

پرسش‌وپاسخ خطی بدون دست‌وپنجه نرم کردن با FSM:

```python
from badking import Bot, Dispatcher, F, ConversationManager

bot = Bot("TOKEN")
dp = Dispatcher()
convos = ConversationManager()
dp.register_middleware(convos)

@dp.message(F.text == "/register")
async def register(message, bot):
    async with convos.conversation(bot, message.chat.id) as conv:
        await conv.send("اسم کاملت چیه؟")
        name = await conv.get_response(timeout=60)

        await conv.send("شماره تماس؟")
        phone = await conv.get_response(timeout=60)

        await conv.send(f"ثبت شد ✅\nنام: {name.text}\nتلفن: {phone.text}")

asyncio.run(bot.polling(dp))
```

اگر کاربر جواب ندهد، `ConversationTimeout` می‌گیری. اگر چت دیگری پیام بدهد، مزاحم مکالمه نمی‌شود.

### ۲. منوی چندصفحه‌ای (KeyboardPaginator)

```python
from badking import KeyboardPaginator, F

products = ["کتاب پایتون", "هدفون", "ماوس", "کیبورد", "مانیتور", "لپ‌تاپ"]
paginator = KeyboardPaginator(products, per_page=3, prefix="shop", columns=1)

@dp.message(F.text == "/shop")
async def shop(message, bot):
    await bot.send_message(
        message.chat.id, "محصولی انتخاب کن:",
        reply_markup=paginator.markup(page=0).model_dump(exclude_none=True),
    )

@dp.callback_query(F.data.startswith("shop:"))
async def on_shop(cq, bot):
    parsed = paginator.parse(cq.data)
    if not parsed:
        return
    kind, value = parsed
    if kind == "page":
        await bot.edit_message_text(
            cq.message.chat.id, cq.message.message_id, "محصولی انتخاب کن:",
            reply_markup=paginator.markup(page=value).model_dump(exclude_none=True),
        )
    elif kind == "item":
        await bot.answer_callback_query(cq.id, f"انتخاب شد: {products[value]}")
```

دکمه‌های «قبلی / بعدی» و شماره صفحه خودکار ساخته می‌شوند.

### ۳. FSM پایدار با SQLite

```python
from badking import Bot, Dispatcher, F, State, StatesGroup, SQLiteStorage

class Order(StatesGroup):
    item = State()
    address = State()

dp = Dispatcher(storage=SQLiteStorage("orders.db"))
bot = Bot("TOKEN")

@dp.message(F.text == "/order")
async def start_order(message, state):
    await state.set_state(Order.item)
    await bot.send_message(message.chat.id, "چه چیزی می‌خواهی؟")

@dp.message(Order.item)
async def get_item(message, state):
    await state.update_data(item=message.text)
    await state.set_state(Order.address)
    await bot.send_message(message.chat.id, "آدرس تحویل؟")

@dp.message(Order.address)
async def get_address(message, state):
    data = await state.get_data()
    await state.clear()
    await bot.send_message(
        message.chat.id,
        f"سفارش ثبت شد ✅\nکالا: {data['item']}\nآدرس: {message.text}",
    )
```

ربات را ری‌استارت کن — state سر جایش است.

### ۴. دستیار هوشمند با ابزار

```python
from badking import AIAssistant, OpenAICompatibleLLM

llm = OpenAICompatibleLLM(
    base_url="https://api.openai.com/v1",
    api_key="sk-...",
    model="gpt-4o-mini",
)

assistant = AIAssistant(
    llm,
    persona="دستیار فروشگاه، مودب و کوتاه جواب بده",
    tools=[check_order_status, get_price],   # توابع خودت
)

answer = await assistant.reply(user_key=str(message.from_user.id), text=message.text)
await bot.send_message(message.chat.id, answer)
```

مدل خودش تصمیم می‌گیرد کدام ابزار را صدا بزند. اگر ابزار خطا بدهد، کل مکالمه نمی‌شکند.

### ۵. RAG روی مستندات خودت

```python
from badking import SimpleRAG, AIAssistant, OpenAICompatibleLLM

rag = SimpleRAG()
rag.add_text(open("faq.txt", encoding="utf-8").read(), source="faq")
rag.add_text(open("policies.txt", encoding="utf-8").read(), source="policies")

assistant = AIAssistant(OpenAICompatibleLLM(...), rag=rag)
# حالا ربات از محتوای فایل‌های تو جواب می‌دهد، نه از خودش
```

### ۶. اتصال به هر سرویس خارجی

```python
from badking import Connector, Auth

zarinpal = Connector(
    base_url="https://api.zarinpal.com",
    auth=Auth(type="bearer", token="..."),
    retries=3,
)

result = await zarinpal.post("/pg/v4/payment/request.json", json_body={
    "merchant_id": "....",
    "amount": 50000,
    "callback_url": "https://example.com/callback",
})
```

Retry خودکار روی 5xx و 429، با احترام به `Retry-After`.

### ۷. پرداخت داخل بله

```python
from badking import PaymentToolkit

pay = PaymentToolkit(bot)

await pay.send_invoice(
    chat_id=message.chat.id,
    title="کتاب پایتون",
    description="نسخه چاپی، ارسال رایگان",
    payload="order-1234",
    provider_token="...",
    prices=[{"label": "کتاب", "amount": 500000}],
)
```

### ۸. مینی‌اپ با اعتبارسنجی امن

```python
from badking import validate_init_data

# در سرور مینی‌اپ، initData را از کلاینت بگیر
data = validate_init_data(init_data_from_client, bot_token="123456:ABC...")
print(data.user.id, data.user.first_name)   # امضا تأیید شد
```

الگوریتم دقیقاً مطابق مستندات رسمی بله: فیلدها الفبایی مرتب، با `\n` متصل، HMAC-SHA256.

---

## Self-bot — اکانت شخصی، نه ربات

این بخش همان چیزی است که aiobale دارد و بیشتر مردم دنبالش هستند: کار با
اکانت شخصی بله، نه توکن بازو.

```bash
pip install "badking[hybrid]"
badking login --phone 09123456789 --session me.session
```

```python
from badking import SelfBot

async with SelfBot(session="me.session") as bot:
    print(await bot.get_me())

    # ارسال از اکانت شخصی
    await bot.send_message("@my_channel", "سلام از BADKING")

    # تاریخچه کامل
    async for msg in bot.iter_messages("@my_channel", limit=500):
        print(msg.date, msg.text)

    # واکنش، حذف، فوروارد، تایپ
    await bot.react("@my_channel", 12345, "❤")
    await bot.delete_messages("@my_channel", [12345])
    await bot.forward_messages("@dest", [12345], from_peer="@src")
    await bot.send_typing("@my_channel")
```

رویدادها:

```python
@bot.on(lambda m: m.text == "/ping")
async def ping(msg):
    await msg.reply("pong")

await bot.run_until_disconnected()
```

**۷۹ RPC** با اسکیما و شماره فیلد واقعی — دقیقاً همان‌هایی که کلاینت بله
استفاده می‌کند، نه بیشتر و نه کمتر:

```bash
badking rpc                          # لیست همه ۷۹ متد
badking rpc --service groups         # ۲۷ متد گروه و کانال
badking rpc --search واکنش           # جستجو در نام و توضیح
badking rpc --describe messaging.SendMessage   # اسکیمای کامل یک متد
```

### هر RPC، حتی آن‌هایی که در جدول نیستند

```python
# با نام و اسکیما
await bot.call("messaging.LoadHistory",
               peer={"type": 4, "id": 123, "accessHash": 456},
               offset_date=-1, load_mode=2, limit=20)

# بدون اسکیما، با شماره فیلد خام — برای متدهایی که بله بعداً اضافه می‌کند
await bot.raw_call("messaging.SomeNewMethod", {1: peer_bytes, 2: 5})

# کشف متد ناشناخته
await bot.probe("messaging.SomeNewMethod")

# دیدن اسکیما از داخل کد
bot.describe("messaging.SendMessage")
bot.search("واکنش")
```

### ساختار پیام، همان‌طور که بله می‌خواهد

```python
from badking.hybrid import make_text_content, make_chat, make_peer

# MessageContent{15: TextMessage{1: value}} — نه {"textMessage": ...}
content = make_text_content("سلام")
chat = make_chat("channel", 123)
peer = make_peer("channel", 123, access_hash=456)
```

`raw_call` همان دری است که aiobale ندارد: اگر بله متد جدیدی اضافه کند و در
جدول ما نباشد، بدون آپدیت کتابخانه صدایش می‌زنی.

### اگر بله پروتکل را عوض کرد

شماره فیلدها در یک JSON است، نه پراکنده در کد:

```bash
export BADKING_RPC_SCHEMA=/path/to/schema.json
```

بدون آپدیت کتابخانه. این تفاوت اصلی با هر پیاده‌سازی دیگری است.

> ⚠️ **ریسک:** این لایه غیررسمی است. ممکن است اکانتت مسدود شود. با شماره
> جداگانه کار کن. جزئیات کامل در [`badking/hybrid/README.md`](badking/hybrid/README.md).

---

## ربات بدون نوشتن کد

```bash
badking new mybot       # ساخت پروژه کامل
badking dry-run         # تست جریان بدون توکن
badking codegen         # تبدیل flow.json به کد پایتون
badking setup           # تنظیم توکن
badking run             # اجرا
```

`flow.json` را با Notepad ویرایش کن:

```json
{
  "start": "welcome",
  "steps": {
    "welcome": {"type": "message", "text": "سلام! 👋", "next": "ask_name"},
    "ask_name": {"type": "ask", "text": "اسمت چیه؟", "save": "name", "next": "done"},
    "done": {"type": "message", "text": "خوش آمدی {name}!"}
  }
}
```

بدون یک خط پایتون، یک ربات مکالمه‌ای داری. وقتی بزرگ شد، `badking codegen` همان جریان را به کد تبدیل می‌کند.

---

## سه لایه دسترسی

| لایه | مخاطب | ابزار |
|---|---|---|
| **۰ — بدون کد** | صاحب کسب‌وکار | Flow Builder، CLI، dry-run |
| **۱ — پایتون** | برنامه‌نویس | Dispatcher، FSM، Filter، AI، Connector، Conversation |
| **۲ — خام** | مهندس | `bot.request("anyMethod", {...})` — هر متد، هر JSON |

قانون: **هر کاری لایه ۱ می‌کند، لایه ۲ هم می‌کند.** چیزی پنهان نیست.

---

## مقایسه با aiobale

| قابلیت | aiobale | BADKING |
|---|---|---|
| توکن رسمی @botfather | ❌ (لاگین شماره) | ✅ |
| Self-bot / Internal API | ✅ ۷۹ متد | ✅ ۷۹ متد + `raw_call` + `probe` |
| اسکیما قابل override بدون آپدیت | ❌ | ✅ |
| صدا زدن متد ناشناخته (بدون اسکیما) | ❌ | ✅ `raw_call` |
| کشف متد جدید روی سرور | ❌ | ✅ `probe` |
| `describe` / `search` روی RPC ها | ❌ | ✅ |
| FSM + SQLite | ✅ | ✅ |
| Conversation (ویزارد) | ✅ | ✅ |
| KeyboardPaginator | ✅ | ✅ |
| Magic Filter `F` | ✅ | ✅ |
| Middleware + Rate Limit | ✅ | ✅ |
| Webhook Server | ✅ | ✅ |
| MiniApp + HMAC | ❌ | ✅ |
| سفیر (OTP، قالب) | ❌ | ✅ |
| پرداخت فاکتور رسمی | ❌ | ✅ |
| Business API | ❌ | ✅ |
| AI: Tool Calling + RAG | ❌ | ✅ |
| بدون‌کد (Flow Builder) | ❌ | ✅ |
| Connector به هر API | ❌ | ✅ |
| Observability (Prometheus) | ❌ | ✅ |
| Docker + CI آماده | ❌ | ✅ |
| مستندات فارسی | ❌ | ✅ |

---

## ساختار پروژه

```
badking/
├── core/           Bot، Dispatcher، Router، خطاها
├── types/          مدل‌های Pydantic (Message، Update، Keyboard، ...)
├── filters/        Magic Filter F
├── fsm/            State، StatesGroup، FSMContext
├── storage/        Memory، SQLite
├── conversation/   ویزارد پرسش‌وپاسخ
├── keyboards/      KeyboardPaginator
├── miniapp/        اعتبارسنجی HMAC initData
├── safir/          سرویس سفیر (OTP، قالب)
├── payments/       فاکتور و پرداخت
├── business/       Business API
├── ai/             LLM، حافظه، RAG، دستیار
├── flows/          Flow Builder بدون کد
├── connectors/     HTTP به هر سرویس
├── jobs/           Scheduler، JobQueue
├── events/         Event Bus
├── orm/            Store
├── media/          Voice، OCR
├── observability/  Metrics، لاگ JSON
├── security/       AntiSpam، AuditLog، RBAC، Secrets
├── testing/        DryBot، Health
├── middleware/     logging، metrics، antispam
├── ratelimit/      Rate Limiter با اولویت
├── recovery/       Offset Store اتمیک
├── adapters/       Multi-platform
├── compat/         سازگاری aiogram/PTB
└── hybrid/         Self-bot (ایزوله، پیش‌فرض خاموش)
```

---

## مرز صادقانه

این‌ها را باید بدانی، نه اینکه بعداً کشف کنی:

- **هر کاری API رسمی بله ندهد، با توکن رسمی از هیچ کتابخانه‌ای برنمی‌آید.** نه BADKING، نه aiobale، نه هیچ‌کس دیگر.
- **تاریخچه کامل پیام‌ها** (قدیمی‌تر از ۲۴ ساعت) با توکن رسمی ممکن نیست. `iter_messages` ما آپدیت‌های موجود را می‌پیماید. برای تاریخچه کامل، لایه hybrid لازم است.
- **Self-bot ریسک دارد.** لایه `hybrid` پیش‌فرض خاموش است و بدون `ack_risk=True` فعال نمی‌شود. دلیلش: Internal API غیررسمی است، می‌شکند، و می‌تواند اکانت شخصی‌ات را ببندد. ببین [`badking/hybrid/README.md`](badking/hybrid/README.md).
- **شماره فیلدهای پروتکل داخلی، رسمی نیست.** هیچ‌کس آن‌ها را از بله نگرفته. تفاوت BADKING این است که همه در یک جدول JSON است و با `BADKING_RPC_SCHEMA` بدون آپدیت کتابخانه عوض می‌شود.
- **اعدادی مثل «۴۰۹۶ کاراکتر» یا «حذف تا ۴۸ ساعت»** در مستندات رسمی بله نیامده‌اند. در BADKING پیش‌فرض قابل‌تنظیم‌اند و از `retry_after` واقعی سرور یاد می‌گیرند.
- **Self-bot کامل پیاده‌سازی شده.** ۷۹ RPC با اسکیما و شماره فیلد واقعی (تطابق کامل با کلاینت رسمی بله)، ورود با شماره + کد SMS، تاریخچه، ارسال متن و فایل، واکنش، گروه و کانال، مخاطبین، کیف پول، رویدادها. ۸۸ تست آفلاین.

---

## مستندات

- 🌐 **[docs.badking.ir](https://docs.badking.ir)** — مستندات کامل فارسی
- 📘 [`docs/bale-api.md`](docs/bale-api.md) — خلاصه مستندات رسمی بله
- 🗺️ [`docs/roadmap.md`](docs/roadmap.md) — نقشه راه و وضعیت فازها
- ⚠️ [`badking/hybrid/README.md`](badking/hybrid/README.md) — هشدار self-bot
- 🚀 [`START_HERE.md`](START_HERE.md) — راهنمای قدم‌به‌قدم برای شروع

---

## تست

```bash
python -m pytest tests/ -q     # 98 passed
```

تست‌ها شامل وکتورهای قراردادی مستقل برای HMAC، تست رگرسیون برای باگ‌های ممیزی، و تست‌های end-to-end با mock server هستند.

---

## مشارکت

این پروژه توسط **دانیال شهرکی** ([@badking-daniyal](https://github.com/badking-daniyal)) ساخته و نگهداری می‌شود.

Issue و PR باز است. اگر باگ پیدا کردی، بگو — ممیزی کد بخشی از فرهنگ این پروژه است.

**Contributors:** [badking-daniyal](https://github.com/badking-daniyal)

---

## مجوز

MIT — آزاد برای استفاده، تغییر و فروش.

badking.ir
