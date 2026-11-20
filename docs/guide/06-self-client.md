# Self Client (Self-bot)

**Warning:** uses Bale's unofficial internal protocol. Account ban risk.

```python
from badking.hybrid import SelfBot, SessionManager

mgr = SessionManager("sessions.bks", password="...")
session = mgr.get("user:123")

async with SelfBot(session=session) as sb:
    me = await sb.get_me()
```

## Methods

| Method | Signature | Description |
|---|---|---|
| `get_me` | `(self) -> 'Peer'` | اطلاعات اکانت خودمان. |
| `get_full_me` | `(self) -> 'dict[str, Any]'` | اطلاعات کامل اکانت: آیدی، نام، شماره، یوزرنیم. |
| `get_wallet` | `(self) -> 'dict[str, Any]'` | موجودی کیف پول اکانت. |
| `send_message` | `(self, ref: 'str | int | Peer', text: 'str', reply_to: 'int | None' = None, silent: 'bool' = False) -> 'Message'` | ارسال پیام متنی از اکانت شخصی. |
| `send_file` | `(self, ref: 'str | int | Peer', path: 'str', caption: 'str | None' = None) -> 'Message'` | آپلود و ارسال فایل از اکانت شخصی. |
| `edit_message` | `(self, ref: 'str | int | Peer', message_id: 'int', text: 'str') -> 'bool'` | ویرایش پیام — RPC واقعی UpdateMessage است، نه EditMessage. |
| `delete_messages` | `(self, ref: 'str | int | Peer', message_ids: 'list[int]', revoke: 'bool' = True) -> 'bool'` | حذف پیام. |
| `forward_messages` | `(self, to: 'str | int | Peer', message_ids: 'list[int]', from_peer: 'str | int | Peer') -> 'bool'` | فوروارد — RPC واقعی ForwardMessages (جمع) است. |
| `react` | `(self, ref: 'str | int | Peer', message_id: 'int', code: 'str') -> 'bool'` | گذاشتن واکنش — سرویس ABACUS، نه reactions. |
| `get_reactions` | `(self, ref: 'str | int | Peer', message_id: 'int') -> 'dict'` | واکنش‌های یک پیام. |
| `mark_read` | `(self, ref: 'str | int | Peer') -> 'bool'` | علامت‌گذاری خوانده‌شده. |
| `send_typing` | `(self, ref: 'str | int | Peer') -> 'bool'` | شروع تایپ — سرویس PRESENCE، نه messaging. |
| `pin_message` | `(self, ref: 'str | int | Peer', message_id: 'int') -> 'bool'` | سنجاق پیام. |
| `create_group` | `(self, title: 'str', users: 'list[dict] | None' = None, channel: 'bool' = False, username: 'str | None' = None) -> 'dict'` | ساخت گروه یا کانال. |
| `get_group` | `(self, ref: 'str | int | Peer') -> 'dict'` | اطلاعات کامل گروه. |
| `join_group` | `(self, token: 'str') -> 'dict'` | ورود به گروه با لینک دعوت. |
| `leave_group` | `(self, ref: 'str | int | Peer') -> 'bool'` | ترک گروه. |
| `get_members` | `(self, ref: 'str | int | Peer', limit: 'int' = 100) -> 'dict'` | لیست اعضای گروه. |
| `get_contacts` | `(self) -> 'dict'` | لیست مخاطبین. |
| `block_user` | `(self, user_id: 'int') -> 'bool'` | مسدود کردن کاربر. |
| `edit_name` | `(self, name: 'str') -> 'bool'` | تغییر نام پروفایل. |
| `get_messages` | `(self, ref: 'str | int | Peer', limit: 'int' = 100) -> 'list[Message]'` |  |
| `iter_messages` | `(self, ref: 'str | int | Peer', limit: 'int | None' = None, batch: 'int' = 50, reverse: 'bool' = False) -> 'AsyncIterator[Message]'` | پیمایش تاریخچه پیام‌ها با صفحه‌بندی خودکار. |
| `get_dialogs` | `(self, limit: 'int' = 100) -> 'list[Dialog]'` |  |
| `report_chat` | `(self, chat_id: 'int', chat_type: 'int' = 3, reason: 'str' = 'محتوای نامناسب') -> 'bool'` | گزارش یک چت. |
| `raw_call` | `(self, full_name: 'str', fields: 'dict[int, Any]', service: 'str | None' = None) -> 'dict[int, list[Any]]'` | صدا زدن RPC با شماره فیلد خام، بدون نیاز به اسکیما. |
| `probe` | `(self, full_name: 'str') -> 'dict[str, Any]'` | Check whether a method exists in the LOCAL registry. |
| `describe` | `(self, full_name: 'str') -> 'dict[str, Any]'` | اسکیمای یک متد: فیلدها، شماره‌ها، پاسخ، و هشدار خطر. |
| `search` | `(self, term: 'str') -> 'list[str]'` | جستجوی متد با کلمه کلیدی. |

## BLOCKED

Field numbers, framing, and method routing are **not verified** against a
live server. See `docs/SELF_CLIENT_AUDIT.md`.
