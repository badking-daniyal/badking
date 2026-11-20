# Authentication

## Bot token

```python
bot = Bot("123456789:ABC...")
```

## Self-bot OTP

```python
from badking.hybrid import SessionManager

mgr = SessionManager("sessions.bks", password="secret")
result = await mgr.request_code("09123456789")
# send SMS code
result = await mgr.submit_code("09123456789", "12345")
```

Two-step (2FA) accounts set `needs_password=True`.

## BLOCKED

Real endpoints, SMS delivery, and error codes cannot be verified without a
real phone number.
