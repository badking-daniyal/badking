# Quick Start

```python
from badking import Bot, F

bot = Bot("123456789:TOKEN")

@bot.on_message(F.text == "/start")
async def start(message):
    await message.reply("سلام!")

await bot.run()
```

Get the token from [@botfather](https://ble.ir/botfather) in Bale.

## Without a token

```python
from badking.testing import DryBot

bot = DryBot()
await bot.send_message(1, "hi")
assert len(bot.sent_messages) == 1
```
