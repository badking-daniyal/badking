# Middleware

```python
from badking import BaseMiddleware

class Timing(BaseMiddleware):
    async def before(self, update, bot, data):
        data["t0"] = time.time()

dp.register_middleware(Timing().as_middleware())
```

Built-ins: `logging_mw`, `metrics_mw`, `antispam_mw`.
