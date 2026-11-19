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
feat: protocol enums, utils, keyboard builders, typed CallbackData

Closes the remaining gap with aiobale's non-RPC surface, and goes past it
where the original is thin.

enums/ (16 files worth, one module):
  PeerType, ChatType, GroupType, ListLoadMode, TypingMode, SendType,
  PrivacyMode, Restriction, ReportKind, GivingType, GiftOpenning,
  PeerSource, SendCodeType, AuthErrors. IntEnum, so they pass straight
  into field numbers. Alternate spellings from the official client
  (VOICERECODRING, CHOSINGGIF, CHOSINGEMOJI, GiftOpening) resolve to the
  same values.

utils/:
  smart_split_text   split long messages without breaking words
  generate_id        random_id for CreateGroup / SendMessage
  extract_join_token / extract_username
  decode_int64_list / encode_int64_list   raw varint lists from the server
  Throttle           rate-limited calls with retry
  create_progress_bar / format_bytes
  to_persian_digits / to_english_digits / normalize_phone
  CallbackData       typed button payloads, no pydantic

keyboards/builder.py:
  InlineKeyboardBuilder with url / callback_data / copy_text / web_app
  ReplyKeyboardBuilder with request_contact / request_location

Also fixed a flaky scheduler test that assumed 0.1s was enough under load;
it now polls for the condition instead of sleeping a fixed time.

273 tests pass, twice in a row, all offline.
"@
& $git commit -m $msg -q
& $git log --format="%h %an" -1
Write-Output "=== PUSH ==="
& $git push origin main 2>&1 | Out-String
Write-Output "=== VERIFY ==="
& $git ls-remote origin refs/heads/main
