# File Management

```python
data = await bot.download_file(file_id)      # bytes
await bot.send_document(chat_id, "path.pdf")
```

Self-bot upload: `SelfBot.send_file()`. Download in self-bot is **not
implemented** (`files.GetNasimFileUrl` is registered but has no client method).
