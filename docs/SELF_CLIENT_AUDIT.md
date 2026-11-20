# BADKING Self Client — ممیزی مستقل

**تاریخ:** 2026-11-20
**روش:** ۳ ممیزی مستقل (read-only) + تأیید عملی با اجرای کد
**دامنه:** `badking/hybrid/` — auth, session, transport, client, rpc, schema, proto, plugin

---

## خلاصه اجرایی

یافتهها به سه دسته تقسیم شدند:

1. **باگهای واقعی تأییدشده با اجرا** → رفع شدند + regression test
2. **ادعاهای مستندات که با کد همخوان نبودند** → اصلاح شدند
3. **مواردی که بدون حساب واقعی قابل تأیید نیستند** → صریحاً BLOCKED

**تعداد تستها:** ۱۰۲۶ (پس از اضافه شدن ۲۵ regression test)

---

## یافتههای تأییدشده و رفعشده

| # | یافته | شواهد | رفع |
|---|---|---|---|
| F1 | `_my_id` قبل از انتقال session محاسبه میشد → همیشه 0، `get_me()` stub، `is_out` اشتباه | اجرا: `SelfBot(session=Session(user_id=42))._my_id == 0` | محاسبه بعد از session + بهروزرسانی بعد از login |
| F2 | `get_wallet` دو بار تعریف شده، سرویس `abacus` اشتباه (رجیستری `kifpool` دارد) | اجرا: `registry.get("abacus.GetMyKifpools") → KeyError` | حذف تعریف مرده، سرویس `kifpool` |
| F3 | `make_chat("user"/"chat")` خطا میداد → ارسال پیام به کاربر/چت ناممکن | اجرا: `ValueError: نوع chat ناشناخته: user` | پذیرش هر دو نگاشت PEER_TYPE و CHAT_TYPE |
| F4 | متدهای گروه `peer=` میفرستادند ولی اسکیما `group=` میخواهد → `KeyError` محلی | اجرا: `get_group → keys: ['peer']` | `_short_peer()` و کلیدهای مطابق اسکیما |
| F5 | `block_user`, `check_username`, `edit_about`, `add_contact` کلید اشتباه | اسکیمای رجیستری | اصلاح به `peer`, `nick_name`, `{value}`, `{user_id,type}` |
| F6 | `edit_profile` متد مرده `users.EditProfile` صدا میزد | `registry.get → KeyError` | تجزیه به `EditName`/`EditNickName`/`EditAbout` |
| F7 | `send_message`/`send_file` با `date` bytes crash میکردند | کد: `float(resp.get("date"))` | تبدیل ایمن bytes→int/float |
| F8 | `send_file` وقتی URL نبود silently پیام با file_id=0 میفرستاد | کد: `if upload_url:` | خطای صریح `SelfBotError` |
| F9 | `_upload_bytes` بدون httpx silently return میکرد | کد: `logger.warning; return` | پرتاب خطای روشن |
| F10 | `probe` هربار بایت خالی میفرستاد و وجود متد را حدس میزد | کد: `rpartition` بدون استفاده | بررسی رجیستری محلی + `server_verified: False` |
| F11 | `websockets>=12.0` unpinned → در 14+ `extra_headers` شکسته | نصب محلی 12.0، مستندات websockets | محدود به `<14.0` |
| F12 | `leave_by_id` فیلد `type` را در ShortPeer میفرستاد (اسکیما ندارد) | `ShortPeer={id,accessHash}` | اصلاح به `{id,accessHash}` |

---

## وضعیت هر حوزه

### Authentication و OTP — PARTIALLY_VERIFIED
- **پیادهشده:** نرمالسازی شماره، device fingerprint، `request_code`، `sign_in`، `refresh`، جریان دو مرحلهای، SessionManager
- **تست آفلاین:** فقط توابع خالص (`normalize_phone`, `device_fingerprint`) پوشش دارند
- **BLOCKED:** endpoint واقعی، شماره فیلدها، SMS، کدهای خطای واقعی، صحت 2FA
- **ناسازگاری شناختهشده:** `auth.py` جدول فیلد جداگانه دارد (`code=3`) در حالی که `schema.py` میگوید `code=2`. **BLOCKED** — بدون ترافیک واقعی نمیتوان تعیین کرد کدام درست است.

### Session Persistence و Encryption — IMPLEMENTED (با محدودیت)
- **پیادهشده:** PBKDF2-HMAC-SHA256 (200k)، XOR stream + HMAC، atomic write، چند اکانت، export/import zip با checksum
- **تست آفلاین:** roundtrip، رمز اشتباه، فایل خراب، JWT expiry، چند اکانت
- **محدودیت صادقانه:** رمزنگاری دستساز است (نه AEAD)، MAC فقط body را میپوشاند، و checksum zip احراز هویت نیست. پیشفرض بدون رمز، متن آشکار است.
- **BLOCKED:** اعتبار توکن واقعی، اینکه بله اصلاً JWT صادر میکند یا نه

### Connection و Reconnection — IMPLEMENTED (با ریسک)
- **پیادهشده:** framing، rate limiting، reconnect با backoff، request/response matching
- **BLOCKED:** framing واقعی (length-prefixed حدس است)، convention `req_id` در فیلد 1 (حدس است)
- **ریسک شناختهشده:** `_handle_drop` pending futures را fail میکند ولی replay نمیکند؛ `RpcFailed` هرگز پرتاب نمیشود.

### Message Operations — IMPLEMENTED (پس از رفع باگها)
- **پیادهشده:** send/edit/delete/forward/react/views/pin/typing/online
- **تست آفلاین:** ۲۵ regression test جدید
- **BLOCKED:** صحت شماره فیلدها و پاسخ سرور

### Message History و Iterators — IMPLEMENTED (با محدودیت)
- **پیادهشده:** `iter_messages` با dedup و pagination، `iter_dialogs`
- **محدودیت:** `reverse=True` فقط داخل هر صفحه معکوس میکند؛ cursor مبتنی بر ثانیه است
- **BLOCKED:** رفتار واقعی سرور با `offset_date=-1`

### Chat و Channel Management — IMPLEMENTED (پس از رفع باگها)
- تمام متدها اکنون کلیدهای مطابق اسکیمای رجیستری میفرستند
- **BLOCKED:** صحت معنایی `group_type` و ShortPeer در سرور واقعی

### Media Operations — PARTIALLY_IMPLEMENTED
- **پیادهشده:** آپلود سه مرحلهای، خطای صریح وقتی URL نیاید
- **BLOCKED:** صحت `GetNasimFileUploadUrl`، فرمت POST، و **هیچ متد download در hybrid وجود ندارد** (`files.GetNasimFileUrl` رجیستری هست ولی متدی نیست)

### RPC Registry و Execution — IMPLEMENTED
- ۷۹ متد، ۶۵ پاسخ، override با env
- **محدودیت صادقانه:** منبع «استخراج از aiobale» فقط ادعای متنی است — نه سورس aiobale در workspace هست، نه `.proto`، نه generator، نه citation در schema.py. شماره فیلدها **تأییدنشده**اند.
- `probe` اکنون صادقانه فقط رجیستری محلی را چک میکند

### Inline Callback — NOT_IMPLEMENTED در Self Client
- `make_inline_keyboard` وجود دارد ولی فراخوانده نمیشود و کلید `rows` در اسکیما نیست
- `@bot.on` update parser عملاً Message تولید نمیکند (decode بدون schema → nested bytes)
- callback در **لایه ربات رسمی** (`core/bot.py`) پیاده است، نه self-bot
- **BLOCKED:** فرمت واقعی callback update

### Error Handling — PARTIALLY_IMPLEMENTED
- دو سلسلهمراتب جدا: `transport.py` و `core/errors.py` — hybrid از دومی استفاده نمیکند
- `RpcFailed` و `RateState.learn` کد مردهاند
- **BLOCKED:** اینکه سرور اصلاً error frame با code میفرستد یا نه

### Protocol Compatibility — IMPLEMENTED (کدک) / BLOCKED (سازگاری)
- کدک protobuf واقعی است: varint، wire types، unknown field preservation
- **باگ شناختهشده:** wire types 1 و 5 با فرمت integer decode میشوند نه float
- **BLOCKED:** تطابق با وایر واقعی بله

---

## نتیجه صادقانه

Self Client **یک پیادهسازی واقعی و قابل آزمایش آفلاین است**، نه Fake. ولی:

- صحت پروتکل (شماره فیلدها، framing، method routing) **تأییدنشده** و BLOCKED است.
- ادعای «دقیقاً همان ۷۹ RPC کلاینت بله» یک ادعای متنی است، نه اثباتشده.
- کاربر نباید بدون حساب واقعی، آن را «آماده production» بداند.

---

## Regression Tests

`tests/test_self_client_audit.py` — ۲۵ تست، تمام آفلاین، هر کدام مربوط به یک یافته بالا.
