# Session Management

```python
from badking.hybrid import SessionManager

mgr = SessionManager("sessions.bks", password="secret")
mgr.list_accounts()
mgr.search("0912")
mgr.export_zip("backup.zip")
mgr.import_zip("backup.zip")
```

## Encryption

PBKDF2-HMAC-SHA256 (200k iterations), XOR stream + HMAC integrity check,
atomic write. **Honest note:** hand-rolled, not AEAD. Without a password the
file is plaintext.

## Backup integrity

`export_zip` writes a SHA256 manifest. `import_zip` rejects a mismatched hash.
This is a checksum, not authentication.
