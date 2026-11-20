# Client API Audit — Self Client (Hybrid)

تاریخ: 2026-11-20 — نسخه 0.2.2

روش: بررسی مستقل کد توسط agentread-only + تأیید دستی file:line. وضعیتها بر اساس
وجود مسیر کد واقعی **و** تست تعیین شدهاند، نه صرفاً وجود کلاس.

| قابلیت | وضعیت | شواهد | توضیح |
|---|---|---|---|
| Dialog Pagination | PARTIALLY IMPLEMENTED → FIXED | `client.py:1053` | cursor اشتباه (row count به جای sortDate) اصلاح شد؛ تست `test_client_api_audit_fixes.py` |
| Message History Pagination | PARTIALLY IMPLEMENTED | `client.py:961` | کار میکند ولی `reverse=True` فقط داخل page است؛ cursor ثانیهای |
| Media Download | NOT IMPLEMENTED | `schema.py:167` | `GetNasimFileUrl` در registry هست ولی متد `SelfBot` وجود ندارد |
| Media Resume | NOT IMPLEMENTED | `schema.py:45` | `chunkSize` تعریف شده ولی استفاده نمیشود |
| Inline Callback | NOT IMPLEMENTED | `rpc.py:161` | `make_inline_keyboard` dead code؛ `answer_callback` وجود ندارد |
| Request Correlation | PARTIALLY IMPLEMENTED → SAFER | `transport.py:326` | stamping فیلد ۱ پروتکل را میشکست؛ پیشفرض خاموش + FIFO correlation |
| RPC Framing | IMPLEMENTED (codec) / wire BLOCKED | `transport.py:58` | 8 تست codec؛ وایر واقعی تأییدنشده |
| Connection Recovery | PARTIALLY IMPLEMENTED | `transport.py:247` | backoff هست ولی `on_disconnect` وصل نشده و تست ندارد |
| Auto Reconnect | PARTIALLY IMPLEMENTED | `client.py:242` | حلقه reconnect هست ولی تستی آنرا اجرا نمیکند |

## باگهای واقعی کشف و اصلاحشده

### 1. Request Correlation پروتکل را میشکست
`_stamp_req_id` فیلد ۱ را به ابتدای **هر** payload اضافه میکرد، در حالی که فیلد ۱
در `SendMessage` / `LoadHistory` داده واقعی است (`peer`, `seq`, `data`). نتیجه:
دو فیلد ۱ با wire type متفاوت در هر درخواست.

**اصلاح**: `stamp_req_id=False` پیشفرض. payload دست نخورده میماند و correlation
داخلی (FIFO) انجام میشود. گزینه `stamp_req_id=True` برای مواردی که پروتکل با
شواهد واقعی تأیید شود باقی ماند.

### 2. `iter_dialogs` cursor غلط
`offset += len(rows)` (شمارش ردیف) به عنوان `offset_date` (فیلد تاریخ) فرستاده
میشد. صفحه ۲ به بعد غلط بود.

**اصلاح**: cursor از `sortDate` آخرین ردیف (فیلد ۳ در schema) گرفته میشود، با
محافظت در برابر چرخه تکراری. `_parse_dialog` هم `sortDate` را ترجیح میدهد.

## موارد BLOCKED (بدون شواهد سرور)

- تأیید اینکه بله واقعاً req_id را در فیلد ۱ میفرستد یا خیر
- تأیید framing واقعی (length-prefixed در برابر raw)
- معنای دقیق `offset_date` و `exclude_pinned` در `LoadDialogs`
- رفتار reconnect در برابر قطع واقعی اینترنت

این موارد بدون ترافیک سرور قابل تأیید نیستند و نباید Complete اعلام شوند.
