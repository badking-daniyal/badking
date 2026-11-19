$ErrorActionPreference = "Stop"
Set-Location "D:\AI\badking"

& "C:\Program Files\Git\cmd\git.exe" add -A
if ($LASTEXITCODE -ne 0) { throw "git add failed" }

$msg = @(
  "feat: close spec gaps - storage, media, moderation, migration, bilingual docs",
  "",
  "- RedisStorage + PostgreSQLStorage with TTL, health, purge (optional deps)",
  "- MediaEngine: download/upload/progress/cache/validation, path-traversal safe",
  "- Moderator + ChannelMonitor: warn/mute/ban, escalation, audit, stats",
  "- Migration Toolkit: badking migrate converts aiobale projects safely",
  "- Bilingual docs (fa/en) with parity tests; 27 examples; 915 tests",
  "- CLI: build_parser() extracted; migrate subcommand added",
  "- Version 0.2.0; extras postgres/all; CHANGELOG updated"
) -join "`n"

& "C:\Program Files\Git\cmd\git.exe" commit -m $msg
if ($LASTEXITCODE -ne 0) { throw "git commit failed" }

& "C:\Program Files\Git\cmd\git.exe" log -1 --format="%H %s"
