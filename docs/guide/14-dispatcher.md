# Dispatcher

```python
from badking import Bot, Dispatcher

dp = Dispatcher()
bot = Bot("TOKEN")

@dp.message(F.text)
async def echo(message, bot):
    await bot.send_message(message.chat.id, message.text)

await bot.polling(dp)
```

Handlers receive `(message, bot)`.
