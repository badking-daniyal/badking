# Migration from aiobale

```bash
badking migrate analyze ./project
badking migrate ./project --dry-run
badking migrate ./project
```

Rewrites imports, renames methods, renames names in the body (avoids
`NameError`), and lists everything it could not convert.

Mapping: `migration/mappings.json` with 4 statuses.

**Verified on a real project:** 4/4 files syntax+import valid. See
`docs/MIGRATION_VALIDATION.md`.
