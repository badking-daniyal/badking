# Access Control Audit — Secure Default Permissions

**تاریخ:** 2026-11-20

---

## تناقض قبلی

قبل از این مرحله:

```python
SelfBot(permissions=None)  # → self.permissions = None → هیچ چک مجوزی
```

یعنی **نبود Permission به معنای دسترسی نامحدود** بود. این نقض صریح «Deny by Default» است.

---

## اصلاح انجامشده

### رفتار جدید

```python
SelfBot(...)                          # → PermissionPolicy() خالی → Deny ALL
SelfBot(permissions=PermissionPolicy(allow={"send_messages"}))
                                      # → فقط ارسال پیام مجاز
SelfBot(legacy_unrestricted=True)     # → رفتار قدیمی + هشدار امنیتی
```

| حالت | `permissions` | `legacy_unrestricted` | هشدار |
|---|---|---|---|
| پیشفرض | `PermissionPolicy()` خالی | `False` | ❌ |
| Policy صریح | policy دادهشده | `False` | ❌ |
| Legacy opt-in | `None` | `True` | ✅ `InsecureLegacyModeWarning` |

پیام هشدار صریحاً میگوید: «فقط برای سازگاری با کد قدیم است و برای Production توصیه نمیشود.»

---

## پوشش تمام مسیرهای حساس

| بررسی | نتیجه |
|---|---|
| مسیرهای مستقیم `transport.request` | ۲ (`call` + `raw_call`) — **هر دو چک مجوز دارند** |
| متدهای حساس (`send_message`, `delete_messages`, `kick_user`, ...) | ۴۴ متد، همگی از `self.call()` میگذرند |
| `_upload_bytes` (HTTP مستقیم) | توسط `send_file` صدا میشود که چک `media_upload` دارد |
| تست ساختاری | `test_no_direct_transport_request_outside_call_and_raw_call` |
| تست ساختاری | `test_permission_check_present_in_both_paths` |

**هیچ مسیر حساسی از بررسی مجوز عبور نمیکند.**

---

## تستهای Negative

`tests/test_access_control_audit.py` (۹ تست) + `tests/test_self_client_security.py`:

- `test_call_denied` — `call` با policy خالی رد میشود
- `test_raw_call_denied` — `raw_call` رد میشود
- `test_all_dangerous_rpcs_denied` — تمام RPC خطرناک رد میشوند
- `test_no_permission_equals_deny_all` — نبود مجوز ≠ دسترسی نامحدود
- `test_legacy_requires_explicit_flag` + هشدار
- `test_default_policy_is_empty`

---

## تستهای آپدیتشده (حذف نشدهاند)

| فایل | تغییر |
|---|---|
| `tests/test_hybrid.py` | fixture `make_bot` حالا `PermissionPolicy.full()` میدهد |
| `tests/test_self_client_reliability.py` | تست integration policy کامل میدهد |
| `tests/test_self_client_security.py` | تست «سازگاری» به «deny-by-default» تبدیل + تست legacy |

هیچ تستی حذف یا غیرفعال نشد.

---

## وضعیت نهایی

| مورد | وضعیت |
|---|---|
| Deny by Default | ✅ IMPLEMENTED + TESTED |
| نبود Permission ≠ دسترسی نامحدود | ✅ IMPLEMENTED + TESTED |
| Legacy opt-in صریح | ✅ IMPLEMENTED + TESTED |
| هشدار امنیتی Legacy | ✅ IMPLEMENTED + TESTED |
| تمام مسیرهای حساس چک مجوز | ✅ VERIFIED |
| Negative tests | ✅ ۹ تست |
