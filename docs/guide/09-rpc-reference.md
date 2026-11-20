# RPC Reference

```bash
badking rpc                     # list all
badking rpc --service groups    # filter
badking rpc --search reaction   # search
badking rpc --describe messaging.SendMessage
```

## Registry

`badking.hybrid.rpc.registry` — 79 methods, 65 response schemas.

## Override

```bash
set BADKING_RPC_SCHEMA=my_schema.json
```

## BLOCKED

Field numbers are **not verified** against a live server. The claim that they
match aiobale is prose only — no source, `.proto`, or generator is present.
