# Architecture

```
badking/
├── core/          Bot, Dispatcher, Router, errors
├── types/         Message, User, Chat, keyboards
├── filters/       Magic filters (F)
├── fsm/           State, StatesGroup, FSMContext
├── storage/       Memory, SQLite, Redis, PostgreSQL
├── middleware/    BaseMiddleware + builtins
├── keyboards/     Builders, pagination
├── media/         MediaEngine
├── moderation/    Moderator, ChannelMonitor
├── security/      Secrets, AuditLog, SecurityScanner
├── compat/        Migration Center, BaleMethod
├── hybrid/        Self-bot: auth, session, transport, rpc, client
├── plugins/ i18n/ jobs/ observability/ testing/ cli/
```

## Boundary

Bot API (`core/`) and Self Client (`hybrid/`) are separate. The self-bot
does not depend on the bot layer and vice versa.
