# Plugins

```python
from badking import Plugin, PluginManager

class MyPlugin(Plugin):
    name = "my"
    version = "1.0.0"
    async def setup(self, bot): ...
    async def teardown(self): ...

manager = PluginManager()
manager.register(MyPlugin())
await manager.setup_all(bot)
```
