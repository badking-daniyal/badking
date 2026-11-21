# ممیزی SSRF و DNS Rebinding در دانلود رسانه

تاریخ: 2026-11-21 · نسخه: 0.2.2 · وضعیت کلی: **IP Pinning پیادهسازی و اثبات شد (`VERIFIED`)**

## ۱. وضعیت پیش از اصلاح — آسیبپذیری واقعی

کد قبلی در `badking/hybrid/download.py` تنها `socket.getaddrinfo` را در لحظه
اعتبارسنجی فراخوانی میکرد و سپس `httpx.AsyncClient` با DNS معمولی اتصال میزد.
یعنی:

1. **DNS Rebinding آزاد بود**: بین resolve در `validate_download_url` و connect
   در httpx فاصله زمانی وجود داشت. یک DNS مخرب میتوانست ابتدا IP عمومی و سپس
   `127.0.0.1` برگرداند. خود docstring قبلی صریحاً مینوشت «فعلاً BLOCKED است».
2. **رنجهای ناقص**: پرچمهای `ipaddress` بهتنهایی `100.64.0.0/10` (CGNAT)،
   `192.0.0.0/24` و `198.18.0.0/15` را «خصوصی» علامت نمیزدند.
3. **userinfo و پورت بررسی نمیشدند**: `http://user:pass@host/` و پورتهای
   داخلی (مثل 6379، 3306، 8080) قابل ارسال بودند.
4. **Proxy محیطی**: `trust_env=True` پیشفرض httpx به `HTTP_PROXY` /
   `HTTPS_PROXY` / `ALL_PROXY` اجازه میداد مسیر اتصال را دور بزنند.

## ۲. راهکار پیادهای: IP Pinning با حفظ TLS/SNI

فایل جدید `badking/hybrid/ssrf.py`:

- `resolve_validated_ips(url)` → `(host, port, ips)`: تمام IPها را با لیست
  کامل رنجهای خطرناک بررسی میکند. IPv4-mapped IPv6 صریحاً رد میشود.
- `PinnedAsyncBackend.connect_tcp` → به جای hostname، دقیقاً به IP تأییدشده
  وصل میشود. hostname اصلی در `httpcore.URL` (Origin) باقی میماند.
- `PinnedAsyncTransport` → `AsyncConnectionPool` را با backend پینشده میسازد؛
  الگوی `AsyncResponseStream` httpx را برای جریان دانلود رعایت میکند.
- `build_pinned_transport(url)` → transport پینشده یا `None` (وقتی DNS دردسترس
  نباشد؛ حفظ رفتار نسخه قبل).

**چرا TLS/SNI حفظ میشود؟** httpcore در `_async/connection.py` هنگام
`connect_tcp` از `origin.host` و هنگام `start_tls` از
`sni_hostname or origin.host` بهعنوان `server_hostname` استفاده میکند. چون ما
Origin را دستکاری نمیکنیم و تنها بکاند را هدایت میکنیم، هدر `Host` و SNI همان
hostname اصلی میمانند و اعتبارسنجی گواهی معمولی انجام میشود.

**Proxy**: `httpx.AsyncClient(..., trust_env=False, transport=pinned)` — متغیرهای
proxy محیطی نمیتوانند اتصال را از مسیر پینشده خارج کنند.

**Redirect**: هر مرحله دوباره `validate_download_url` میشود و transport جدید
پینشده ساخته میشود. حداکثر ۵ ریدایرکت و Timeout کلی (`total_timeout`) و سقف
حجم (`max_size`) و نوشتن اتمیک بدون تغییر باقی ماندند.

## ۳. سناریوهای آزمایششده

| سناریو | نتیجه |
|---|---|
| DNS عمومی / خصوصی / چند IP با یکی خصوصی | `VERIFIED` |
| CGNAT، benchmarking، IPv4-mapped، loopback v6 | `VERIFIED` |
| userinfo، پورت داخلی، scheme غیر HTTP | `VERIFIED` |
| اتصال واقعی Socket: DNS جعلی به `127.0.0.1`، پین به `127.0.0.2` | `VERIFIED` |
| حفظ `Host: cdn.test` در سرور مقصد | `VERIFIED` |
| ریدایرکت به `127.0.0.1` مسدود شد | `VERIFIED` |
| مسیر `download_file`transport پینشده میسازد | `VERIFIED` |
| Fail-Closed: شکست DNS / پاسخ خالی / رکورد نامعتبر / Timeout → استثنا، صفر AsyncClient بدون pinning | `VERIFIED` |
| ریدایرکت به دامنه با DNS نامعتبر → متوقف، بدون اتصال جایگزین | `VERIFIED` |
| Cancellation هنگام اتصال پینشده + عدم باقی ماندن Task | `VERIFIED` |
| وابستگی به API داخلی httpx/httpcore صریح و تستشده | `VERIFIED` |

**بازبینی Fail-Closed (2026-11-21):** در پیادهسازی قبلی سه حلقه fail-open وجود
داشت: `resolve_validated_ips` هنگام شکست DNS لیست خالی برمیگرداند،
`build_pinned_transport` در آن صورت `None` میداد، و `_client_for` AsyncClient
معمولی بدون transport میساخت. اکنون هر سه مسیر استثنا میدهند و تنها
AsyncClientای ساخته میشود که transport پینشده داشته باشد.

تستها: `tests/test_ssrf_ip_pinning.py`، `tests/test_ssrf_live_socket.py`،
`tests/test_ssrf_download_integration.py`، `tests/test_ssrf_fail_closed.py`،
`tests/test_ssrf_transport_compat.py`. سرور محلی تست، آفلاین و بدون حساب واقعی
است. تست زنده اینترنتی: **BLOCKED** (بدون حساب مجاز).

**وابستگی به API داخلی:** IP Pinning از سه API استفاده میکند:
`httpcore.AsyncConnectionPool(network_backend=...)` (عمومی در httpcore 1.x)،
`httpx._transports.default.AsyncResponseStream` (داخلی httpx، برای Streaming)
و `httpcore._backends.auto.AutoBackend` (داخلی httpcore). تست
`test_ssrf_transport_compat.py` وجود و امضای آنها را بررسی میکند تا تغییر
API در ارتقای وابستگیها زود دیده شود. نسخههای آزمایششده: httpx 0.28.1 /
httpcore 1.0.9.

## ۴. محدودیتها و ریسکهای باقیمانده

- `NOT VERIFIED`: رفتار دقیق TLS/SNI با گواهی واقعی Bale روی شبکه زنده
  (نیاز به حساب/اتصال مجاز). منطق از سورس httpcore 1.0.9 استنتاج و با سرور
  محلی HTTP اثبات شد، ولی handshake TLS زنده آزمایش نشد.
- `NOT VERIFIED`: Windows و Linux هر دو توسط CI (Ubuntu) و اجرای محلی
  (Windows) پوشش شدند، ولی bind روی `127.0.0.2` بسته به پیکربندی سیستم است
  (تست در صورت عدم امکان SKIP میشود).
- رنجهای IP آینده ممکن است نیاز به بهروزرسانی لیست `_EXTRA_BLOCKED_NETWORKS`
  داشته باشند.
- `BLOCKED`: Cancellation هنگام Resolve بهصورت آفلاین قابل آزمایش نیست، چون
  `socket.getaddrinfo` مسدودکننده و غیرقابل لغو است. Cancellation هنگام اتصال
  پینشده `VERIFIED` است.
- رفتار Fail-Closed یعنی بدون DNS هیچ دانلودی انجام نمیشود — حتی اگر سرور بله
  URL معتبری بدهد. این یک تغییر رفتاری عمدی و امنیتر از نسخه قبل است.
