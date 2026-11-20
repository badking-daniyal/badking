# Filters

```python
from badking import F

F.text == "/start"
F.text.startswith("/")
F.chat.id == 123
F.from_user.id == 123
F.photo
F.document
F.command("start")
F.regex(r"^/start")
```

## Operators

`&` (AND), `|` (OR), `~` (NOT). Filters can be async and custom.
