# Media Engine

```python
from badking import MediaEngine

engine = MediaEngine(bot, cache_dir=".cache/media", max_size=20*1024*1024)
info = await engine.info(file_id)
engine.validate(info)
path = await engine.download(file_id)
```

`safe_filename()` blocks path traversal. `.exe`/`.sh` rejected.

**Not implemented:** resume for interrupted transfers.
