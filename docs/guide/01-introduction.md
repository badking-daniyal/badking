# Introduction

BADKING is an async Python framework for Bale (بله) messenger bots and
self-clients.

**Version:** 0.2.1 · **Python:** 3.9–3.12 · **Tests:** 1032

## Three access layers

| Layer | What | Entry point |
|---|---|---|
| 0 | No code | `badking new mybot` |
| 1 | Python API | `Bot`, `Dispatcher`, `SelfBot` |
| 2 | Raw protocol | `raw_call`, `raw_fields` |

## Honest limits

- Self-bot uses Bale's **unofficial** internal protocol. Account ban risk is real.
- Field numbers in the RPC registry are **not verified** against a live server (BLOCKED).
- No performance comparison with aiobale has been measured.
