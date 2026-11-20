# Types Reference

| Type | Module | Fields |
|---|---|---|
| `Message` | `badking.types.message` | message_id, date, chat, from_user, text, caption, photo, document, ... |
| `User` | `badking.types.user` | id, is_bot, first_name, last_name, username |
| `Chat` | `badking.types.chat` | id, type, title |
| `CallbackQuery` | `badking.types.callback` | id, from_user, data |

```python
from badking import Message, User, Chat
```
