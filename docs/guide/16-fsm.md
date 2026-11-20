# FSM

```python
from badking import State, StatesGroup, FSMContext

class Order(StatesGroup):
    item = State()
    address = State()
```

Storage: `MemoryStorage`, `SQLiteStorage`, `RedisStorage`, `PostgreSQLStorage`.
