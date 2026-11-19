$ErrorActionPreference = "Stop"
Set-Location "D:\AI\badking"
& "C:\Program Files\Git\cmd\git.exe" add -A
if ($LASTEXITCODE -ne 0) { throw "git add failed" }
& "C:\Program Files\Git\cmd\git.exe" commit -m "chore: remove temporary helper script"
if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
& "C:\Program Files\Git\cmd\git.exe" push origin main
if ($LASTEXITCODE -ne 0) { throw "git push failed" }
