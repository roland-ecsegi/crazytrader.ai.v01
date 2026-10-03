# Phase5 cancellation adversarial review

Separate root adversarial pass; not separate-model or human approval. No Phase5 gate.

Verified boundaries: exact registry tenant/account/portfolio/order/client/origin intent/mode;
current actor permission and policy bundle; remote DENY cannot be overridden; offline
fallback requires matching explicit owner setting; no market/P&L dependency; no LIVE SDK
endpoint/credentials. Authorization record binds full request/context hashes and identities.
Clock expiry and nonmonotonic transitions prevent sends. Claim/audit failure rolls back
before transport; after claim, ambiguity/interruption retains funds and never resends the
same request. Query-only financial settlement handles filled/cancel races and unposted fees.

Repairs: full context/authorization identity validation added; event catalog synchronized;
fixture signatures now cryptographically checked, not just presence; migration triggers
made rerunnable. Original ALLOW policy evidence is audited as ALLOW even if the local
claim expiry check subsequently prevents dispatch; it is evidence, not a perpetual grant.

Pending: real venue cancellation client alias behavior, complete account query coverage,
full financial/venue rule scope and incident resolution. Explicit new cancel requests
require fresh policy; no hidden retry of an existing claim. Test runner API stays internal.
