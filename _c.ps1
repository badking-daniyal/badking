$ErrorActionPreference = "Continue"
$env:PERCH_GIT_ATTRIBUTION = "off"
$env:GIT_AUTHOR_NAME = "badking-daniyal"
$env:GIT_AUTHOR_EMAIL = "d099173878@gmail.com"
$env:GIT_COMMITTER_NAME = "badking-daniyal"
$env:GIT_COMMITTER_EMAIL = "d099173878@gmail.com"
$git = "C:\Program Files\Git\cmd\git.exe"
Set-Location "D:\AI\badking"

& $git add -A
$msg = @"
feat: full error hierarchy, resilience engine, and doctor CLI

The two things developers complain about most in existing Bale libraries:
unclear errors, and no way to diagnose a broken setup. Both addressed.

errors.py - rewritten from 66 lines to a real hierarchy:
  BADKINGError root with error_code, method, hint, cause, retryable.
  40+ specific classes across auth, connection, rate limit, permission,
  message, media, validation, protocol, storage, config.
  Every class carries a `hint` that says what to DO, not what went wrong.
  diagnose() produces a report ready to paste into an issue.
  format_exception() strips tokens and hex secrets before printing.
  raise_for_response() maps server codes and reads the description text
  for flood/admin/chat-not-found/message-too-long variants.
  Legacy names BaleError, BadRequestError, StopPropagation kept so
  nothing that imported them breaks.

resilience.py - new:
  RetryPolicy   fixed/linear/exponential backoff, jitter, and it refuses
                to retry non-retryable errors (a bad argument stays bad).
                Respects server retry_after over its own delay.
  CircuitBreaker closed/open/half-open, cooldown, success threshold.
  RequestQueue  concurrency cap + rate cap + max_pending backpressure.
  ResilientCaller  queue -> breaker -> retry, in that order, so three
                retries count as one breaker failure, not three.

cli/doctor.py - new:
  badking doctor  checks python, package, optional deps, token, .env,
                  session file, write access, disk, git, and network.
                  Prints check marks and a fix hint per failure.
  badking info    version, exports, RPC count, feature availability.
  badking check   syntax-checks every .py in a project, skips __pycache__.
  badking test    runs pytest.

362 tests pass, all offline.
"@
& $git commit -m $msg -q
& $git log --format="%h %an" -1
Write-Output "=== PUSH ==="
& $git push origin main 2>&1 | Out-String
Write-Output "=== VERIFY ==="
& $git ls-remote origin refs/heads/main
