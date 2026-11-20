# aiobale 0.3.9 — Protocol Fixture

This directory contains the `methods/` source tree of **aiobale 0.3.9**, used
strictly as a **protocol reference fixture** for verifying BADKING's RPC field
numbers in `tests/test_protocol_verification.py`.

- **Source:** `aiobale_py 0.3.9` (installed package in the project backup)
- **License:** MIT — see [`LICENSE`](LICENSE)
- **Copyright:** (c) 2025 Alireza Jahani | Enalite LD; (c) 2026 Mohammadamin Madani

No code from this fixture is imported by BADKING at runtime. It is only parsed
by tests to compare `pydantic Field(alias="N")` numbers against
`badking/hybrid/schema.py`. This preserves attribution and satisfies the
mission's intellectual-property rule (section 31).
