# Self Client Reliability — وضعیت واقعی

**تاریخ:** 2026-11-20
**قاعده:** هر قابلیت فقط در صورتی IMPLEMENTED نامیده میشود که تست مربوطه وجود داشته باشد.

---

| قابلیت | وضعیت | شاهد (فایل / تست) |
|---|---|---|
| Connection Recovery | IMPLEMENTED | `transport.py::_handle_drop` — backoff نمایی ۱→۳۰s، حداکثر ۵ تلاش؛ `test_hybrid.py` |
| Request Timeout | IMPLEMENTED | `transport.py::request` → `RpcTimeout`؛ `test_self_client_reliability.py` |
| Retry Policy | IMPLEMENTED | `resilience.py::RetryPolicy` — ۴ تست در `test_resilience.py` |
| Flood Wait | IMPLEMENTED | `RateState.learn()` + `parse_rpc_error` → `retry_after`؛ ۳ تست |
| RPC Error Mapping | IMPLEMENTED | `reliability.py::raise_for_rpc_error` → `RpcFailed(code, retry_after)`؛ ۶ تست |
| Request Correlation | IMPLEMENTED | `_stamp_req_id` / `_peek_req_id` + Future dict؛ ۳ تست |
| `req_id` | IMPLEMENTED | فیلد 1 varint (قرارداد حدسی — مستند در `PROTOCOL_VERIFICATION.md`) |
| Connection Framing | IMPLEMENTED | `length` و `raw` — ۵ تست |
| Graceful Shutdown | IMPLEMENTED | `transport.py::close()` — idempotent، fail pending، cancel reader؛ ۱ تست |
| Circuit Breaker | IMPLEMENTED | `resilience.py` — تست در `test_resilience.py` |
| Message dedup | NOT_IMPLEMENTED | — |
| Server-side session recovery | BLOCKED | نیاز به حساب واقعی |

---

## جزئیات پیادهسازیهای جدید

### RPC Error Mapping

پاسخ سرور حالا قبل از decode بررسی میشود:

```python
frame = await transport.request(payload)
raise_for_rpc_error(frame)   # ← خطاهای 429/401/503 به RpcFailed تبدیل میشوند
return decode_response(spec, frame)
```

کدهای شناختهشده: `429` (flood), `400/401/403` (auth), `500/502/503/504` (server).

### Flood Wait

- `RateState` از قبل نرخ ارسال را محدود میکند
- حالا `retry_after` سرور هم توسط `parse_rpc_error` استخراج میشود
- `RpcFailed.retry_after` در اختیار کاربر قرار میگیرد تا طبق آن صبر کند

### تستها

`tests/test_self_client_reliability.py` — ۱۷ تست:
- ۵ تست framing (تک قاب، قاب ناقص، دو قاب)
- ۳ تست correlation
- ۶ تست error mapping
- ۱ تست integration (client → RpcFailed)
- ۲ تست timeout/shutdown

---

## BLOCKED — نیاز به حساب واقعی

| مورد | دلیل |
|---|---|
| صحت `req_id` روی wire | نیاز به capture ترافیک واقعی |
| Connection Recovery در قطع واقعی اینترنت | نیاز به اتصال زنده |
| Flood Wait واقعی سرور | نیاز به حساب آزمایشی |
| Server-side session restore | نیاز به حساب آزمایشی |

هیچیک از اینها ادعای TESTED نشدهاند.
