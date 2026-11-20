# BADKING API Reference

مرجع سریع تمام APIهای عمومی. جزئیات کامل در [سایت مستندات](https://docs.badking.ir).

---

## Bot API

```python
from badking import Bot, F

bot = Bot("123456:TOKEN")

@bot.on_message(F.text == "/start")
async def start(message):
    await message.reply("سلام")

await bot.run()
```

### متدهای پیام
`send_message`, `send_photo`, `send_video`, `send_audio`, `send_voice`,
`send_document`, `send_animation`, `send_contact`, `send_location`,
`send_sticker`, `send_poll`, `send_media_group`, `send_chat_action`,
`edit_message_text`, `delete_message`, `forward_message`, `copy_message`

### متدهای چت
`get_chat`, `get_chat_member`, `get_chat_member_count`,
`get_chat_administrators`, `ban_chat_member`, `unban_chat_member`,
`restrict_chat_member`

### متدهای Callback و Webhook
`answer_callback_query`, `set_webhook`, `delete_webhook`, `get_webhook_info`,
`set_my_commands`, `get_updates`, `polling`

### فایل
`get_file`, `download_file`

---

## Self Client (Self-bot)

```python
from badking.hybrid import SelfBot, SessionManager

mgr = SessionManager("sessions.bks", password="...")
session = mgr.get("user:123")

async with SelfBot(session=session) as sb:
    me = await sb.get_me()
    wallet = await sb.get_wallet()
    await sb.send_message("@channel", "سلام")
```

### متدها
`get_me`, `get_full_me`, `get_wallet`, `get_entity`, `send_message`,
`send_file`, `edit_message`, `delete_messages`, `forward_messages`,
`react`, `set_reaction`, `remove_reaction`, `get_reactions`, `get_views`,
`mark_read`, `send_typing`, `stop_typing`, `set_online`, `pin_message`,
`unpin_message`, `get_pinned`, `clear_history`, `create_group`, `get_group`,
`join_group`, `join_by_link`, `leave_group`, `leave_by_id`, `invite_users`,
`kick_user`, `get_members`, `get_invite_link`, `get_group_preview`,
`get_contacts`, `add_contact`, `block_user`, `unblock_user`, `edit_name`,
`edit_about`, `check_username`, `get_messages`, `iter_messages`,
`get_dialogs`, `iter_dialogs`, `report_chat`, `upvote`,
`raw_call`, `probe`, `describe`, `search`

---

## FSM و Storage

```python
from badking import State, StatesGroup, FSMContext
from badking.storage import RedisStorage

class Order(StatesGroup):
    item = State()
    address = State()

storage = RedisStorage("redis://localhost:6379/0", ttl=3600)
```

Storageها: `MemoryStorage`, `SQLiteStorage`, `RedisStorage`, `PostgreSQLStorage`

---

## فیلترها

`F.text`, `F.caption`, `F.photo`, `F.video`, `F.document`, `F.voice`,
`F.audio`, `F.sticker`, `F.location`, `F.contact`, `F.animation`,
`F.chat.id`, `F.chat.type`, `F.from_user.id`, `F.from_user.username`,
`F.text.startswith()`, `F.text.endswith()`, `F.text.contains()`,
`F.text.regexp()`, `F.data`, `F.command()`

عملگرها: `&` (AND)، `|` (OR)، `~` (NOT)

---

## کیبوردها

```python
from badking import InlineKeyboardBuilder, ReplyKeyboardBuilder

kb = InlineKeyboardBuilder()
kb.button("بلی", callback_data="yes")
kb.button("خیر", callback_data="no")
kb.adjust(2)
markup = kb.as_markup()
```

---

## Media Engine

```python
from badking import MediaEngine, MediaError

engine = MediaEngine(bot, cache_dir=".cache/media", max_size=20*1024*1024)
info = await engine.info(file_id)
engine.validate(info)
path = await engine.download(file_id, on_progress=cb)
```

---

## Moderation

```python
from badking import Moderator, link_rule, Action

mod = Moderator(bot, warn_limit=3)
mod.add_rule(link_rule(Action.WARN))
await mod.inspect(message)
```

---

## امنیت

```python
from badking import SecurityScanner, Secrets

report = SecurityScanner().scan(".")
print(report.summary())
token = Secrets().get("TOKEN")
```

CLI: `badking security scan .`

---

## Migration

```bash
badking migrate analyze ./project
badking migrate aiobale ./project --dry-run
badking migrate aiobale ./project
```

نگاشت: `migration/mappings.json`

---

## Testing

```python
from badking.testing import DryBot

bot = DryBot()
await bot.send_message(123, "سلام")
assert len(bot.sent_messages) == 1
```

---

**نسخه:** 0.2.0 · **تستها:** ۹۹۳ · **Python:** ۳.۹–۳.۱۲
