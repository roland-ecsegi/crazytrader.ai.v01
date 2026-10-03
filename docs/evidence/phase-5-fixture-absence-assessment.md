# Bounded fixture absence source assessment

L0; no Phase5 gate, release, retry, account health or certification grant.

The unmodified official SDK performs a dummy-auth literal-loopback signed order
lookup. A response hook retains the bounded raw HTTP object/status without altering
the SDK request, forwarding credentials or following redirects. Only an exact400
integer-2013 error object with a message is explicit negative lookup evidence. Empty
errors, timeout, non-400, malformed/mixed order/error or an existing order cannot
be treated as negative. Lookup alone remains insufficient.

A separate bounded complete account/open/orders/fills read covers all configured and
registered symbols from fixture ID zero. Before/after permissions and balances must
be stable; full existing account comparison checks owned history, fills, actual quote,
reservation and attribution. The target must be zero-filled UNKNOWN/recovery without
a known venue ID; other unresolved requests, internal state/config change, financial
mismatch, incomplete/stale source or presence reject the assessment. Original request,
lookup and account source are PostgreSQL-bound with NULL-safe hash/content checks.
Raw sources commit before comparison/audit; final typed assessment/event/outbox is
atomic. Assessment explicitly has financial_effect NONE and certification_effect NONE.

The pending-state health/final-claim fence now covers SDK as well as native dispatches.
Source assessment does not clear that fence or historical incidents. Captured snapshot
absence does not prove a paused original sender cannot later submit, nor establish
real Binance history retention or queued processing completion. Before financial
release/controlled retry, implement the original send deadline and late-acceptance
fence and revalidate fresh authoritative coverage. No blind retry or unknown release.

Actual initial6 lookup/assessment cases PASS (31.36s), plus standalone signed lookup
PASS (8.48s). Full83 cases PASS (285.88s) and one concurrent-deposit fixture identifier failure;
repaired final8 cases PASS (34.99s).175 units/mypy55/134 schemas/scan/offline SDK/
wheel-sdist PASS;17 platform/ledger PASS (6.27s). No owner credentials or external order.
