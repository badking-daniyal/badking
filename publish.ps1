# BADKING — اسکریپت انتشار روی GitHub
# فقط کافی است یوزرنیم گیتهابت و نام مخزنی که میخواهی بسازی را بدهی.
# موقع push، پنجره لاگین GitHub باز میشود (Git Credential Manager).

$env:PYTHONIOENCODING = "utf-8"
$git = "C:\Program Files\Git\cmd\git.exe"
if (-not (Test-Path $git)) { $git = "C:\Program Files\Git\bin\git.exe" }

Set-Location $PSScriptRoot

Write-Host ""
Write-Host "=== انتشار BADKING روی GitHub ===" -ForegroundColor Cyan
Write-Host ""

$username = Read-Host "یوزرنیم GitHub تو"
$repo = Read-Host "نام مخزن (مثلا badking)"

if ([string]::IsNullOrWhiteSpace($username) -or [string]::IsNullOrWhiteSpace($repo)) {
    Write-Host "یوزرنیم و نام مخزن نمیتواند خالی باشد." -ForegroundColor Red
    exit 1
}

$remoteUrl = "https://github.com/$username/$repo.git"

Write-Host ""
Write-Host "ریموت: $remoteUrl" -ForegroundColor Yellow
Write-Host ""

# حذف ریموت قبلی در صورت وجود
$existing = & $git remote get-url origin 2>$null
if ($existing) { & $git remote remove origin }

& $git remote add origin $remoteUrl
if ($LASTEXITCODE -ne 0) { Write-Host "خطا در اضافه کردن ریموت" -ForegroundColor Red; exit 1 }

& $git branch -M main

Write-Host ""
Write-Host "در حال push... اگر پنجره لاگین GitHub باز شد، وارد حسابت شو." -ForegroundColor Cyan
Write-Host ""

& $git push -u origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "push ناموفق بود. معمولا دلیلش احراز هویت است." -ForegroundColor Red
    Write-Host "اگر مخزن خصوصی است یا توکن لازم است، دوباره تلاش کن و از PAT استفاده کن." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "تمام! مخزن تو اینجاست:" -ForegroundColor Green
Write-Host "https://github.com/$username/$repo" -ForegroundColor Green
Write-Host ""
