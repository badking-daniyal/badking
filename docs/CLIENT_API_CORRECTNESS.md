# صحت Client API — Pagination، Message Parsing و Response Schema

> تاریخ: ۲۰۲۶-۱۱-۲۱ · نسخه: ۰.۲.۲
> وضعیت تست: **Mock/Offline** — هیچ ادعای Live Verification وجود ندارد.

این سند رفتار **قابل پیشبینی** `iter_dialogs`، `iter_messages` و تجزیهٔ پیامها را شرح میدهد.
همهٔ شماره فیلدها از سورس **aiobale 0.3.9** استخراج شدهاند. این سورس **منبع مقایسه** است،
**نه اثبات پروتکل رسمی بله یا رفتار سرور زنده**. موارد نیازمند ترافیک واقعی صریحاً
`BLOCKED` علامت خوردهاند.

---

## ۱. `iter_dialogs(ref, limit, batch)`

**RPC:** `messaging.LoadDialogs` · **پاسخ:** `{3: [PeerData]}`

| رفتار | توضیح |
|---|---|
| اولین درخواست | `offset_date=0`، `limit=batch` |
| مکاننمای صفحه بعد | `sortDate` آخرین ردیف خام (`PeerData.field 3`) — **هرگز تعداد ردیفها** |
| صفحه خالی / کلید `dialogs` موجود نباشد | پایان ایمن پیمایش |
| ردیف خراب (غیر dict) | به `Dialog(peer=Peer(id=0))` تبدیل میشود، پیمایش متوقف نمیشود |
| دیالوگ تکراری | با کلید `(peer.type, peer.id)` فیلتر میشود، دوباره تحویل داده نمیشود |
| سرور همان cursor بدهد | بعد از دو درخواست متوقف میشود (جلوگیری از حلقه بینهایت) |
| صفحه کوتاهتر از `limit` | **لزوماً پایان نیست**؛ تا وقتی cursor معتبر است ادامه مییابد |
| `limit` | حتی اگر سرور بیشتر برگرداند رعایت میشود |
| خطای شبکه / Timeout / Cancellation | به caller منتقل میشود، بیصدا پایان نمییابد |

**نکتهٔ پروتکلی:** `sortDate` یک فیلد HISTORY بر حسب ثانیه است، نه شمارش ردیف. استفاده از
تعداد ردیفها بهعنوان cursor بدون شواهد معتبر انجام نشده است.

---

## ۲. `iter_messages(ref, limit, batch, reverse)`

**RPC:** `messaging.LoadHistory` · **پاسخ:** `{1: [MessageData]}`
**درخواست:** `LoadHistory{1: peer, 2: offset_date, 3: load_mode, 4: limit}` · `load_mode=2` (backward)

| رفتار | توضیح |
|---|---|
| اولین درخواست | `offset_date=-1` |
| مکاننمای صفحه بعد | قدیمیترین `date` در صفحه (`MessageData.field 3`) |
| صفحه کاملاً تکراری | پیمایش زود متوقف نمیشود؛ cursor با یک واحد جلو میرود تا چرخه نشکند |
| `messageId=0` | با شمارنده یکتای سراسری علامت میشود، با پیامهای ناشناس دیگر اشتباه گرفته نمیشود |
| پیام تکراری بین صفحات | یکبار تحویل داده میشود |
| `limit` | حتی اگر سرور بیشتر از تعداد درخواستی برگرداند رعایت میشود |
| `reverse=True` | ترتیب داخل صفحه برعکس میشود (پیامهای قدیمیتر اول) |
| مرز صفحات | نه پیام گم میشود نه تکرار (تست اختصاصی) |
| خطای شبکه / Timeout / Cancellation | به caller منتقل میشود |

**محدودیت صادقانه:** معنای دقیق `offset_date` و تضمین عدم ازدسترفتن پیام در مرز صفحات
فقط از سورس aiobale استنباط شده، **نه از ترافیک واقعی سرور بله** → `NOT VERIFIED (Live)`.

---

## ۳. Message Parsing

`MessageData` (aiobale 0.3.9): `senderId=1, messageId=2, date=3, content=4,
repliedTo=8, previousMessage=10, nextMessage=11, editedAt=12`.

`MessageContent` انواع موجود:

| فیلد | شماره | رفتار تجزیه |
|---|---|---|
| `text` | 15 | `TextMessage{1: value}` → `Message.text` |
| `document` | 4 | کپشن (`caption.content`) یا نام فایل → `Message.text`؛ `media_info()` آن را میخواند |
| `serviceMessage` | 11 | `ServiceMessage{1: text, 2: ext}` → `Message.text`، `is_service=True` |
| `botMessage` | 13 | `TemplateMessage.message` → متن داخلی → `Message.text` |
| `gift` | 17 | `GiftPacket.message` (`StringValue`) → `Message.text` |
| `empty` | 5 | `content_type="empty"`، `is_forwarded=True` |

همچنین:
- `repliedTo` → `Message.replied_to` و ویژگی `reply_to_id`
- `editedAt` → `Message.edited_at` و ویژگی `is_edited`
- محتوای ناشناخته **حذف نمیشود**؛ در `Message.raw` دستنخورده باقی میماند
- فیلدهای گم شده / `None` / انواع ناقص → مقدار امن (نه داده ساختگی)
- متنی قابل استخراج نباشد → `text=""` (پر کردن با داده ساختگی ممنوع)

---

## ۴. Dialog Parsing

`PeerData{1: peer, 2: unreadCount, 3: sortDate, 4: senderId, 5: messageId,
6: date, 7: content, 9: firstUnreadMessage, 13: unreadMentions}`.

`_parse_dialog` میخواند: `peer.id`, `peer.type`, `peer.accessHash`, `peer.title`,
`peer.username`, `unreadCount`, `sortDate`/`date`, و آخرین پیام همانند `_parse_message`.
فیلدی که در داده موجود نباشد **حدس زده نمیشود**.

---

## ۵. Response Schema — وضعیت صادقانه

| ساختار | وضعیت | شاهد |
|---|---|---|
| `ServiceMessage{text:1, ext:2}` | IMPLEMENTED | aiobale 0.3.9 `service_message.py` |
| `ServiceExt{giftOpened:18}` | IMPLEMENTED | aiobale 0.3.9 `service_ext.py` |
| `GiftOpened{userId:1, othersCount:2, messageId:3, messageDate:4}` | IMPLEMENTED | همان |
| `GiftPacket{count:1, totalAmount:2, givingType:3, token:4(StringValue), message:5(StringValue), ownerId:6, showAmounts:7(BoolValue)}` | IMPLEMENTED | aiobale 0.3.9 `gift_packet.py` |
| `repliedTo/previousMessage/nextMessage` ساختاریافته | IMPLEMENTED | aiobale 0.3.9 `message_content.py` |
| پاسخ خالی RPC (`{seq, date}`) | عمداً Schema اضافه نشد — پاسخ عمومی است | `RESPONSES` موجود |

**باگ اصلاحشده:** `GiftPacket` دو بار تعریف شده بود؛ تعریف دوم (scalar) بر تعریف دقیق
غلبه میکرد و `token`/`message`/`showAmounts` را بهجای wrapperهای `StringValue`/`BoolValue`
بهصورت scalar رمزگذاری مینمود. تعریف تکراری حذف شد. بررسی AST تأیید کرد هیچ کلید تکراری
دیگری در `NESTED` / `RESPONSES` / `SERVICES` وجود ندارد.

تست round-trip از `encode_named` و `decode` واقعی با schema حلشده استفاده میکند و باینر
خروجی را میسنجد (`decode` خام رشتهها را بهعنوان `bytes` برمیگرداند — رفتار صحیح wire-level).

---

## ۶. Request Correlation — وضعیت فعلی

پروتکل داخلی بله **شناسهٔ درخواست (req_id) را در پیامها تأیید نمیکند**. بنابراین:

- `stamp_req_id=False` پیشفرض است؛ اضافه کردن req_id حدسی ممنوع است.
- correlation مبتنی بر FIFO است، ولی **فقط برای یک اتصال و درخواستهای سریالی** قابل اطمینان است.
- پاسخ خارج از ترتیب، پاسخ دیرهنگام و update بین پاسخها → **BLOCKED / NOT VERIFIED** بدون ترافیک واقعی.
- رفتار قابلپیشبینی فعلی: درخواستها به ترتیب ارسال و به ترتیب مصرف میشوند؛ هیچ پاسخی به درخواست
  اشتباه تخصیص داده نمیشود مگر اینکه سرور ترتیب را نقض کند (که تأیید نشده است).

---

## ۷. Inline Keyboard و Callback

- ساخت کیبورد: `make_inline_keyboard(rows)` — ساختار `Markup{1:[Row{1:[Button]}]}`،
  دکمه `text=1, url=2(wrapped), callbackData=3(wrapped), copyText=9(wrapped)`.
- ارسال در SelfBot: `send_message(..., reply_markup=...)`.
- سازگاری با API قبلی: لیست تخت دکمهها بهعنوان یک ردیف پذیرفته میشود.
- **Callback Query در SelfBot وجود ندارد** — پروتکل داخلی فاقد آن است. ارسال دکمه با
  `callbackData` لزوماً به معنای دریافت callback توسط SelfBot نیست. جزئیات:
  `docs/SELF_INLINE_KEYBOARD.md`.

---

## ۸. محدودیتها و موارد BLOCKED

| مورد | وضعیت |
|---|---|
| معنای دقیق `offset_date` / تضمین مرز صفحات در سرور زنده | NOT VERIFIED (Live) |
| Request Correlation با پاسخ خارج از ترتیب | BLOCKED (نیاز به ترافیک واقعی) |
| Callback Query در SelfBot | BLOCKED (پروتکل داخلی فاقد آن) |
| Media Resume، JWT verification | NOT_IMPLEMENTED / BLOCKED (اسناد قبلی) |
| تست زنده | SKIP — بدون حساب آزمایشی مجاز |

---

## ۹. تستها

`tests/test_client_api_correctness.py` — ۵۱ تست آفلاین:
pagination چندصفحهای، مرز صفحات، پاسخ ناقص/خراب، پیام تکراری، صفحه تماماً تکراری،
`messageId=0`، limit، reverse، network error، timeout، cancellation، parsing تمام انواع
محتوا، dialog parsing، schema field numbers، round-trip باینری.

نتیجهٔ واقعی: **۱۴۱۸ پاس + ۶ SKIP** (کل سوئیت)، exit 0. Mock PASS است، Live PASS نیست.
