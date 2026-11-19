$ErrorActionPreference = "Continue"
$env:PERCH_GIT_ATTRIBUTION = "off"
$git = "C:\Program Files\Git\cmd\git.exe"
Set-Location "D:\AI\badking"

Remove-Item -Force _commit.ps1 -ErrorAction SilentlyContinue
& $git add -A
& $git commit --amend --no-edit -q
& $git log --format="%H%n%an <%ae>%n%cn <%ce>%n---%n%B" -1
Write-Output "=== PUSH ==="
& $git push origin main 2>&1 | Out-String
Write-Output "=== VERIFY ==="
& $git ls-remote origin refs/heads/main
