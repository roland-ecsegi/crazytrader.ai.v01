# Guarded dispatch source/claim review

Separate adversarial root source pass, not separate-model or human approval.

Reviewed paused old sender, signed timestamp/recvWindow, actual immutable deadline,
profile source pin, installation versus claim races, source/event audit atomicity,
legacy requests, SDK/native selection, original scope and header clock. Fixed the
claim race by requiring the exact persisted binding in Python and a matching immutable
transition evidence reference in PostgreSQL. Backend selection and bound installation
serialize by tenant; old requests without a bound are not silently certified/backfilled.
The callback validates the official prepared request without changing its signature.

Repaired tests that expected ACKNOWLEDGED from POST (correct state SUBMITTED until
query recovery), used stale request timestamps for redirect verification, or searched
only the first1000 global pending events for a late tenant. Bounded query read timeout
is distinct from aggressive150ms send/cancel fault injection; zero SDK retries remain.
Added real test-only injected netrc verification; environment auth/proxies disabled.
No credential/URL exception text is exposed. Timed lookup binds original raw HTTP date.

Residual financial requirement: fresh complete source assessment plus bound protocol,
expired signature window and acceptance/read linearization before absence release or
controlled retry. HTTP Date/fixture history is not real Binance processing/retention
proof. Legacy unknown and native result-missing funds stay reserved. No Phase5 gate.
