# Troubleshooting

```bash
badking doctor
badking doctor --verbose
```

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: field not in schema` | wrong kwarg for RPC | `badking rpc --describe <name>` |
| `websockets` TypeError on connect | websockets 14+ | pinned `<14.0` in extras |
| `SessionError: password required` | encrypted file | set `BADKING_SESSION_KEY` |
| `SelfBotError: session invalid` | expired JWT | log in again with SMS |
