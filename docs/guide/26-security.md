# Security

```bash
badking security scan .
badking security scan . --json
```

Severity: CRITICAL, HIGH, MEDIUM, LOW, INFO. Exit code 1 on CRITICAL/HIGH.

```python
from badking import SecurityScanner
report = SecurityScanner().scan(".")
print(report.summary())
```

Detects: hardcoded tokens, private keys, eval/exec, shell=True, SSL disabled,
silent exceptions, asserts.
