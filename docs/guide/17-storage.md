# Storage

| Backend | Import | Extra |
|---|---|---|
| Memory | `MemoryStorage` | — |
| SQLite | `SQLiteStorage` | — |
| Redis | `RedisStorage` | `badking[redis]` |
| PostgreSQL | `PostgreSQLStorage` | `badking[postgres]` |

All implement `get`, `set`, `delete`, `keys`.
