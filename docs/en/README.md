# BADKING — English Documentation

A bot framework for Bale (بله), the Iranian messenger. Async, typed, and built
so that a beginner can ship a bot in ten minutes and a professional can reach
the internal RPC layer when they need to.

**Docs site:** https://docs.badking.ir
**Repository:** https://github.com/badking-daniyal/badking

---

## Install

```bash
pip install badking
```

Optional extras, only if you use them:

```bash
pip install badking[redis]      # RedisStorage
pip install badking[postgres]   # PostgreSQLStorage
pip install badking[all]        # everything
```

Python 3.9 or newer. Windows, macOS, Linux.

## Your first bot

```python
from badking import Bot, F

bot = Bot("123456:ABC...")   # token from @botfather in Bale

@bot.on_message(F.text == "/start")
async def start(message):
    await message.reply("Hello!")

bot.run()
```

Three things to notice:

- `F.text == "/start"` is a filter, not a string comparison you write yourself.
- `message.reply()` knows which chat and which message to answer.
- `bot.run()` handles the connection, reconnects, and shutdown.

## What is in the box

| Area | What you get |
|---|---|
| Core | Async engine, connection manager, auto-reconnect, retry with backoff, rate limiter, request queue, circuit breaker, graceful shutdown, health check |
| Messages | Text, photo, video, file, audio, voice, GIF, sticker, location, contact, album, buttons, scheduled; history, search, edit, delete, forward, copy |
| Events | Message received/edited/deleted, callback, join, leave, member updated, chat updated, connection lost/restored |
| Routing | Router, sub-router, nested router, priorities, stop propagation, handler error isolation |
| Filters | `F.text`, `F.photo`, `F.chat.id`, `F.from_user.id`, `startswith`, `endswith`, `contains`, `regexp`, `command`, `&`, `\|`, `~` |
| FSM | States, groups, context, memory/SQLite/Redis/Postgres storage, TTL, recovery |
| Middleware | Auth, logging, rate limit, anti-spam, database, localization, error, custom; global and per-router |
| Keyboards | Inline, reply, builder, pagination, `CallbackData` factory |
| Media | Download, upload, progress, chunking, cache, validation, path-traversal protection |
| Moderation | Warn, mute, ban, kick, delete, word/link/file filters, escalation, audit log |
| Channel monitor | Join/leave tracking, per-day breakdown, growth stats, multi-channel |
| Storage | Memory, SQLite, Redis, PostgreSQL, custom |
| Plugins | Lifecycle, registry, isolation, error containment |
| i18n | Persian and English catalogs, fallback, placeholder validation |
| Migration | `badking migrate` converts an aiobale project and reports what it could not convert |
| Self-bot | 79 internal RPC methods, 65 response schemas, `raw_call`, `probe`, `describe` |

## Three access layers

**Layer 0 — no code.** `badking new mybot --template shop` generates a working
project. Edit the config, run it.

**Layer 1 — Python.** The API above. This is where most work happens.

**Layer 2 — raw.** `bot.raw_call("some.method", {...})` reaches anything the
protocol exposes, documented or not. Anything Layer 1 does, Layer 2 can do.

## Errors that tell you what to do

Every error carries a code, whether it is retryable, and a hint:

```python
from badking import BADKINGError, format_exception

try:
    await bot.send_message(chat_id, "hi")
except BADKINGError as exc:
    print(format_exception(exc))
    # RateLimitError [RATE_LIMITED] retryable=True retry_after=5.0
    #   → Wait 5 seconds. The server is throttling this bot.
```

The hierarchy:

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

## Resilience, without writing it yourself

```python
from badking import Bot, CircuitBreaker, RequestQueue, ResilientCaller, RetryPolicy

caller = ResilientCaller(
    queue=RequestQueue(concurrency=5, rate=20),
    breaker=CircuitBreaker(failure_threshold=5, cooldown=30),
    policy=RetryPolicy(attempts=3, base_delay=0.5),
)

await caller(bot.send_message, chat_id, "text")
```

Retries with backoff, stops hammering a dead server, queues beyond the rate
limit, and raises the original error when it truly fails.

## CLI

```bash
badking new mybot          # scaffold a project
badking run                # run it
badking test               # run tests
badking doctor             # check environment, token, disk, network
badking info               # version, exports, feature flags
badking check              # validate config
badking migrate . --dry-run  # see what an aiobale migration would change
badking rpc --search photo   # find an RPC method
badking rpc --describe messages.send
badking selfbot            # internal API layer (disabled by default)
```

## Migrating from aiobale

```bash
badking migrate . --dry-run    # report only
badking migrate .              # convert, with .bak backups
```

It rewrites imports, renames methods it is certain about, renames the names in
the body so you do not get a `NameError`, and lists everything it could not
convert. It does not guess.

## Self-bot / internal API

This layer talks to Bale's internal protocol rather than the bot API. It is
isolated in its own module so the rest of the framework does not depend on it.
Pass a phone number for interactive login, or load a saved session:

```python
from badking import SelfBot, hybrid_warning

print(hybrid_warning())  # read the account-ban risk before starting
async with SelfBot(phone="0912...") as client:  # prompts for the SMS code
    me = await client.get_me()
```

**It can get the account banned.** That is the trade. It is isolated in its own
module so the rest of the framework does not depend on it.

What it covers: 79 RPC methods with real field numbers, 65 response schemas,
plus `raw_call` for anything not in the registry, `probe` to discover a method
shape at runtime, and `describe`/`search` to explore the registry.

## Testing

```python
from badking.testing import DryBot

bot = DryBot()
await bot.send_message(1, "hi")
assert bot.sent[-1]["text"] == "hi"
```

876 tests, all offline. No token, no network, no real account.

## Honest limits

- Numbers like "2 messages per second" or "4096 characters" are not in Bale's
  official documentation. They are configurable defaults, not facts.
- Some events the spec asks for are not exposed by Bale's API. Where that is
  true, the framework says so instead of pretending.
- The internal API can change without notice. The transport layer is separate
  and the schema is versioned so a change breaks one module, not the framework.
- There is no public REST API for Perch or for Bale. Everything here is the
  library talking to Bale directly.

## License

MIT. One author: [badking-daniyal](https://github.com/badking-daniyal).
