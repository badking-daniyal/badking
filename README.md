# BADKING

**فریمورک همه کاره، async و AI-Native برای ساخت رباتهای [بله (Bale)](https://www.bale.ai/).**
Superset of aiobale — هر آنچه aiobale دارد، بهتر و بیشتر.

> از کسی که کد بلد نیست تا یک هکر حرفهای: سه لایه دسترسی، بدون محدودیت، و هر چیزی قابل ساخت.

---

## وضعیت: فاز ۱ تا ۹ پیادهسازی شد ✅ — **87 تست پاساند**

| فاز | محتوا | وضعیت |
|---|---|---|
| ۱ | اسکلت، مدلهای Pydantic، Bot/Dispatcher، Long Polling | ✅ |
| ۲ | FSM + Storage، Rate Limit، Update Recovery | ✅ |
| ۳ | MiniApp (HMAC)، سفیر، پرداخت، Business API | ✅ |
| ۴ | AI: حافظه، شخصیت، Tool Calling، Intent، RAG | ✅ |
| ۵ | Flow Builder بدونکد، CLI جادویی، Adapter | ✅ |
| ۶ | Connector عمومی، Scheduler، Job Queue، Event Bus، ORM، Voice/OCR | ✅ |
| ۷ | Observability، امنیت، Dry-run، Health، Docker، CI/CD | ✅ |
| ۸ | لایه Hybrid ایزوله + سازگاری aiogram/PTB | ✅ |
| ۹ | صادرات بسته، لایسنس، مستندات | ✅ |

---

## شروع در ۳۰ ثانیه (بدون توکن)

```bash
pip install -e .
python examples/echo_bot.py --mock
```

خروجی:

```
→ سلام! من ربات BADKING هستم 🤖
→ شما گفتید: سلام دنیا
```

## ربات بدون نوشتن کد

```bash
badking new mybot          # ساخت ربات
badking dry-run            # تست جریان بدون توکن
badking codegen            # تبدیل جریان به کد پایتون
```

فایل `flow.json` را ویرایش کن تا رباتت عوض شود — حتی بدون دانستن پایتون.

## ربات با کد (با توکن `@botfather`)

```python
import asyncio
from badking import Bot, Dispatcher, F

bot = Bot("123456789:TOKEN")
dp = Dispatcher()

@dp.message(F.text == "/start")
async def start(message, bot):
    await bot.send_message(message.chat.id, "خوش آمدید!")

asyncio.run(bot.polling(dp))
```

## دستیار هوشمند (AI-Native)

```python
from badking import AIAssistant, EchoLLM

assistant = AIAssistant(EchoLLM(), persona="دستیار فارسی مودب و کوتاه")
answer = await assistant.reply("user123", "سلام")
```

## ارسال هر چیزی به هر جا (Connector)

```python
from badking import Connector, Auth

api = Connector(base_url="https://api.zarinpal.com", auth=Auth(type="bearer", token="..."))
result = await api.post("/payment/request", json_body={"amount": 1000})
```

## سه لایه دسترسی

1. **لایه صفر (بدون کد)**: Flow Builder، CLI، Dry-run
2. **لایه بالا (پایتون)**: Dispatcher، FSM، Filterها، AI، Connector
3. **لایه خام**: `bot.request("METHOD_NAME", {...})` — دسترسی مستقیم به تمام متدها و JSON خام

هیچ چیزی مخفی نیست. هر کاری لایه بالا میکند، لایه خام هم میکند.

## آنچه BADKING دارد و aiobale ندارد

- توکن رسمی `@botfather` (نه internal API با لاگین شماره)
- MiniApp + اعتبارسنجی HMAC `initData`
- سفیر (OTP، قالب، idempotency)، پرداخت فاکتور رسمی، Business API
- لایه AI کامل (حافظه، شخصیت، Tool Calling، RAG)
- بدونکدی: Flow Builder + CLI + Dry-run
- Connector به هر سرویس خارجی، Multi-platform Adapter
- Observability، امنیت، Docker، CI/CD

## مرز صادقانه

- لایه self-bot (چیزهایی مثل خواندن تاریخچه قدیمی) بهصورت **پلاگین ایزوله و غیرفعال پیشفرض** است — ببینید [`badking/hybrid/README.md`](badking/hybrid/README.md). دلیلش ریسک امنیتی و بسته شدن اکانت است.
- اعدادی مثل «4096 کاراکتر» یا «حذف 48 ساعته» در مستندات رسمی نیامدهاند؛ در BADKING پیشفرض قابلتنظیماند و از `retry_after` سرور یاد میگیرند.

## مستندات

- [`docs/bale-api.md`](docs/bale-api.md) — خلاصه مستندات رسمی بله
- [`docs/roadmap.md`](docs/roadmap.md) — نقشه راه
- [`badking/hybrid/README.md`](badking/hybrid/README.md) — هشدار self-bot

## تست

```bash
python -m pytest tests/ -q     # 87 passed
```

## مجوز

MIT — آزاد برای استفاده، تغییر و فروش.

badking.ir
