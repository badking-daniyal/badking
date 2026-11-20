# Error Reference

```
BADKINGError
├── AuthenticationError
├── ConnectionError
├── TimeoutError
├── NetworkError
├── RateLimitError
├── PermissionError
├── MessageError
├── MediaError
├── SessionError
├── ValidationError
├── ProtocolError
└── StorageError
```

```python
from badking import BADKINGError, format_exception

try:
    await bot.send_message(chat_id, "hi")
except BADKINGError as exc:
    print(format_exception(exc))
```

Self-bot raises `SelfBotError`, `NotConnected`, `RpcTimeout`, `ProtoError`.
