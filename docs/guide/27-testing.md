# Testing

```python
from badking.testing import DryBot

bot = DryBot()
await bot.send_message(123, "hello")
assert len(bot.sent_messages) == 1
```

No token, no network. 1032 offline tests in the project itself.
