# Keyboards

```python
from badking import InlineKeyboardBuilder, ReplyKeyboardBuilder

kb = InlineKeyboardBuilder()
kb.button("Yes", callback_data="yes")
kb.adjust(2)
markup = kb.as_markup()
```

`KeyboardPaginator` handles pagination.
