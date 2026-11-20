# Message Reference

```python
@bot.on_message()
async def handler(message):
    message.text        # str | None
    message.caption     # str | None
    message.chat.id
    message.from_user.id
    message.message_id
    await message.reply("hi")
    await message.delete()
```

## Methods

| Method | Description |
|---|---|
| `reply(text)` | answer this message |
| `answer(text)` | alias of reply |
| `delete()` | delete this message |

Both `reply` and `delete` need a Bot in context (inside Dispatcher).
