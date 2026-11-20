# Routers

```python
from badking import Router

router = Router()

@router.message(F.text == "/help")
async def help_cmd(message):
    await message.reply("help")

dp.include_router(router)
```

Nested routers, priorities, and stop-propagation are supported.
