# BADKING — مستندات فارسی

فریمورک ربات برای بله. ناهمگام، تایپ‌شده، و طوری ساخته شده که یک مبتدی در
ده دقیقه ربات بفرستد و یک حرفه‌ای هر وقت لازم شد به لایه RPC داخلی برسد.

**سایت مستندات:** https://docs.badking.ir
**مخزن:** https://github.com/badking-daniyal/badking

---

## نصب

```bash
pip install badking
```

موارد اختیاری، فقط اگر لازم داری:

```bash
pip install badking[redis]      # RedisStorage
pip install badking[postgres]   # PostgreSQLStorage
pip install badking[all]        # همه
```

پایتون ۳.۹ یا بالاتر. ویندوز، مک، لینوکس.

## اولین ربات

```python
from badking import Bot, F

bot = Bot("123456:ABC...")   # توکن از @botfather در بله

@bot.on_message(F.text == "/start")
async def start(message):
    await message.reply("سلام!")

bot.run()
```

سه چیز که ارزش دیدن دارد:

- `F.text == "/start"` یک فیلتر است، نه مقایسه رشته‌ای که خودت بنویسی.
- `message.reply()` می‌داند به کدام چت و کدام پیام جواب بدهد.
- `bot.run()` اتصال، اتصال مجدد و خاموشی را خودش مدیریت می‌کند.

## داخل جعبه چه هست

| بخش | چه می‌گیری |
|---|---|
| هسته | موتور ناهمگام، مدیریت اتصال، اتصال مجدد، تلاش مجدد با backoff، محدودیت نرخ، صف درخواست، مدارشکن، خاموشی ایمن، بررسی سلامت |
| پیام | متن، عکس، ویدیو، فایل، صوت، ویس، گیف، استیکر، مکان، مخاطب، آلبوم، دکمه، زمان‌بندی؛ تاریخچه، جستجو، ویرایش، حذف، فوروارد، کپی |
| رویداد | پیام دریافتی/ویرایش/حذف، کال‌بک، ورود، خروج، تغییر عضو، تغییر چت، قطع و وصل اتصال |
| مسیریابی | روتر، زیرروتر، روتر تودرتو، اولویت، توقف انتشار، جداسازی خطای هندلر |
| فیلتر | `F.text`، `F.photo`، `F.chat.id`، `F.from_user.id`، `startswith`، `endswith`، `contains`، `regexp`، `command`، `&`، `\|`، `~` |
| FSM | وضعیت، گروه، کانتکست، Storage حافظه/SQLite/Redis/Postgres، TTL، بازیابی |
| میان‌افزار | احراز هویت، لاگ، محدودیت نرخ، ضداسپم، دیتابیس، بومی‌سازی، خطا، سفارشی؛ سراسری و مخصوص روتر |
| کیبورد | شیشه‌ای، معمولی، سازنده، صفحه‌بندی، `CallbackData` |
| رسانه | دانلود، آپلود، پیشرفت، قطعه‌بندی، کش، اعتبارسنجی، محافظت از Path Traversal |
| مدیریت | اخطار، سکوت، اخراج، لگد، حذف، فیلتر کلمه/لینک/فایل، تشدید، لاگ اقدامات |
| نظارت کانال | ثبت ورود و خروج، تفکیک روزانه، آمار رشد، چند کانال |
| ذخیره‌سازی | حافظه، SQLite، Redis، PostgreSQL، سفارشی |
| افزونه | چرخه عمر، ثبت، جداسازی، مهار خطا |
| دو زبان | کاتالوگ فارسی و انگلیسی، fallback، اعتبارسنجی جای‌نگهدار |
| مهاجرت | `badking migrate` پروژه aiobale را تبدیل می‌کند و می‌گوید چه چیزی نشد |
| Self-bot | ۷۹ متد RPC داخلی، ۶۵ اسکیمای پاسخ، `raw_call`، `probe`، `describe` |

## سه لایه دسترسی

**لایه ۰ — بدون کد.** `badking new mybot --template shop` یک پروژه آماده
می‌سازد. تنظیمات را عوض کن، اجرا کن.

**لایه ۱ — پایتون.** همان API بالا. بیشتر کار اینجا انجام می‌شود.

**لایه ۲ — خام.** `bot.raw_call("some.method", {...})` به هر چیزی که
پروتکل ارائه می‌دهد می‌رسد، مستند یا نامستند. هر کاری لایه ۱ می‌کند، لایه ۲
هم می‌کند.

## خطاهایی که می‌گویند چه کار کنی

هر خطا کد دارد، می‌گوید قابل تلاش مجدد است یا نه، و راهنما دارد:

```python
from badking import BADKINGError, format_exception

try:
    await bot.send_message(chat_id, "سلام")
except BADKINGError as exc:
    print(format_exception(exc))
    # RateLimitError [RATE_LIMITED] retryable=True retry_after=5.0
    #   → ۵ ثانیه صبر کن. سرور دارد این ربات را محدود می‌کند.
```

سلسله‌مراتب:

```
BADKINGError
├── AuthenticationError
├── ConnectionError
├── TimeoutError
├── NetworkError
├── RateLimitError
├── PermissionError
├── MessageError
├── MediaError
├── SessionError
├── ValidationError
├── ProtocolError
└── StorageError
```

## تاب‌آوری، بدون اینکه خودت بنویسی

```python
from badking import Bot, CircuitBreaker, RequestQueue, ResilientCaller, RetryPolicy

caller = ResilientCaller(
    queue=RequestQueue(concurrency=5, rate=20),
    breaker=CircuitBreaker(failure_threshold=5, cooldown=30),
    policy=RetryPolicy(attempts=3, base_delay=0.5),
)

await caller(bot.send_message, chat_id, "متن")
```

تلاش مجدد با backoff، توقف فشار روی سرور خراب، صف وقتی از حد نرخ گذشتی، و
بالا آوردن خطای اصلی وقتی واقعاً شکست خورد.

## CLI

```bash
badking new mybot          # ساخت پروژه
badking run                # اجرا
badking test               # تست
badking doctor             # بررسی محیط، توکن، دیسک، شبکه
badking info               # نسخه، exportها، قابلیت‌ها
badking check              # اعتبارسنجی تنظیمات
badking migrate . --dry-run  # ببین مهاجرت از aiobale چه عوض می‌کند
badking rpc --search photo   # پیدا کردن متد RPC
badking rpc --describe messages.send
badking selfbot            # لایه API داخلی (پیش‌فرض خاموش)
```

## مهاجرت از aiobale

```bash
badking migrate . --dry-run    # فقط گزارش
badking migrate .              # تبدیل، با نسخه پشتیبان .bak
```

importها را عوض می‌کند، متدهایی که مطمئن است را تغییر نام می‌دهد، اسم‌ها را
در بدنه هم عوض می‌کند تا `NameError` نگیری، و هر چیزی که نشد را فهرست
می‌کند. حدس نمی‌زند.

## Self-bot / API داخلی

این لایه با پروتکل داخلی بله حرف میزند، نه با API ربات. در ماژول جدا نگه
داشته شده تا بقیه فریمورک به آن وابسته نباشد. برای ورود تعاملی شماره بدهید،
یا یک session ذخیرهشده بارگذاری کنید:

```python
from badking import SelfBot, hybrid_warning

print(hybrid_warning())  # قبل از شروع، ریسک مسدود شدن اکانت را بخوانید
async with SelfBot(phone="0912...") as client:  # کد SMS را میپرسد
    me = await client.get_me()
```

**می‌تواند اکانت را مسدود کند.** این معامله است. در ماژول جدا نگه داشته شده
تا بقیه فریمورک به آن وابسته نباشد.

چه چیزی پوشش می‌دهد: ۷۹ متد RPC با شماره فیلد واقعی، ۶۵ اسکیمای پاسخ، به‌علاوه
`raw_call` برای هر چیزی که در رجیستری نیست، `probe` برای کشف شکل متد در زمان
اجرا، و `describe`/`search` برای کاوش رجیستری.

## تست

```python
from badking.testing import DryBot

bot = DryBot()
await bot.send_message(1, "سلام")
assert bot.sent[-1]["text"] == "سلام"
```

۸۷۶ تست، همه آفلاین. بدون توکن، بدون شبکه، بدون اکانت واقعی.

## محدودیت‌های صادقانه

- اعدادی مثل «۲ پیام در ثانیه» یا «۴۰۹۶ کاراکتر» در مستندات رسمی بله نیستند.
  پیش‌فرض قابل تغییرند، نه واقعیت.
- بعضی رویدادهایی که در طرح خواسته شده، API بله ارائه نمی‌دهد. هر جا این
  درست باشد، فریمورک می‌گوید، نه اینکه ادای پشتیبانی دربیاورد.
- API داخلی می‌تواند بدون اطلاع عوض شود. لایه Transport جدا است و اسکیما
  نسخه دارد، تا تغییر یک ماژول را بشکند نه کل فریمورک را.
- API عمومی REST نه برای Perch هست نه برای بله. هر چه اینجاست، خود کتابخانه
  است که مستقیم با بله حرف می‌زند.

## مجوز

MIT. یک نویسنده: [badking-daniyal](https://github.com/badking-daniyal).
