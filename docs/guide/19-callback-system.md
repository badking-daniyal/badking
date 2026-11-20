# Callback System

```python
from badking import CallbackData

class Product(CallbackData, prefix="prod"):
    action: str
    product_id: int

data = Product(action="buy", product_id=120)
```

`CallbackFilter` validates incoming data.
