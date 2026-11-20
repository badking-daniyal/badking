# Bot API

```python
from badking import Bot
bot = Bot("TOKEN")
```

## Message methods

| Method | Signature | Description |
|---|---|---|
| `send_message` | `(self, chat_id: 'int | str', text: 'str', *, reply_to_message_id: 'int | None' = None, reply_markup: 'InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | dict | None' = None, disable_web_page_preview: 'bool | None' = None, message_thread_id: 'int | None' = None, **kwargs: 'Any') -> 'Message'` |  |
| `send_photo` | `(self, chat_id: 'int | str', photo: 'str', *, caption: 'str | None' = None, reply_markup: 'Any' = None, **kwargs: 'Any') -> 'Message'` |  |
| `send_video` | `(self, chat_id: 'int | str', video: 'str', **kwargs: 'Any') -> 'Message'` |  |
| `send_audio` | `(self, chat_id: 'int | str', audio: 'str', **kwargs: 'Any') -> 'Message'` |  |
| `send_voice` | `(self, chat_id: 'int | str', voice: 'str', **kwargs: 'Any') -> 'Message'` |  |
| `send_document` | `(self, chat_id: 'int | str', document: 'str', *, caption: 'str | None' = None, reply_markup: 'Any' = None, **kwargs: 'Any') -> 'Message'` |  |
| `send_animation` | `(self, chat_id: 'int | str', animation: 'str', **kwargs: 'Any') -> 'Message'` |  |
| `send_contact` | `(self, chat_id: 'int | str', phone_number: 'str', first_name: 'str', **kwargs: 'Any') -> 'Message'` |  |
| `send_location` | `(self, chat_id: 'int | str', latitude: 'float', longitude: 'float', **kwargs: 'Any') -> 'Message'` |  |
| `send_sticker` | `(self, chat_id: 'int | str', sticker: 'str', **kwargs: 'Any') -> 'Message'` | ارسال استیکر. |
| `send_poll` | `(self, chat_id: 'int | str', question: 'str', options: 'list[str]', **kwargs: 'Any') -> 'Message'` | ارسال نظرسنجی. |
| `send_media_group` | `(self, chat_id: 'int | str', media: 'list[dict[str, Any]]', **kwargs: 'Any') -> 'list[Message]'` | ارسال گروه رسانه (آلبوم). |
| `send_chat_action` | `(self, chat_id: 'int | str', action: 'str') -> 'bool'` |  |
| `edit_message_text` | `(self, chat_id: 'int | str', message_id: 'int', text: 'str', **kwargs: 'Any') -> 'Message'` |  |
| `delete_message` | `(self, chat_id: 'int | str', message_id: 'int') -> 'bool'` |  |
| `forward_message` | `(self, chat_id: 'int | str', from_chat_id: 'int | str', message_id: 'int', **kwargs: 'Any') -> 'Message'` |  |
| `copy_message` | `(self, chat_id: 'int | str', from_chat_id: 'int | str', message_id: 'int', **kwargs: 'Any') -> 'MessageId'` |  |

## Notes

All methods are `async`. Errors raise from `badking.core.errors`.
