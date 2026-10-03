# Guarded fixture dispatch and server clock

L0; no Phase5 gate, real venue credentials/order, absence release or retry.

The official SDK remains unmodified. A validating requests auth callback checks the
prepared signed POST immediately before dispatch: original request expiry, bounded
integer timestamp, fixed5000ms recvWindow, owned client and literal-loopback endpoint.
It returns the exact SDK request without changing the signature. A delayed original
sender past its actual immutable deadline produces UNKNOWN with zero wire submissions;
reservation remains held. SDK send/cancel150ms accepted-timeout faults and zero automatic
retries remain. Queries use bounded1000ms reads, avoiding accidental coupling to the
aggressive submit fault timeout. Missing reads still cannot imply absence or release.

An immutable FixtureDispatchBound pins the complete reviewed child source SHA, SDK3.0.0,
original request/hash/deadline, installation clock and5000ms window. New fixture runner
commits the bound/event/audit/outbox before the single claim; failure cannot claim/send.
Both Python and PostgreSQL require bound evidence on a guarded claim, preventing an old
or unbound caller from using the same authorized request. Repeated installation retains
the original clock/protocol; no lifetime extension. Bound rows cannot be backfilled onto
already started legacy requests. Accounts choose SDK or native backend exclusively;
SQL and tenant serialization protect both choices. No changes to published old contracts.

Captured lookup HTTP Date is retained as an additive clock source, paired with its
original header and existing signed lookup. It is loopback-fixture time, not real
Binance processing/retention or certification evidence. Financial recovery must still
combine a fresh complete absence assessment, original guard bound, elapsed signature
window and the fixture's linearized acceptance/read barrier. No financial effect yet.

Dummy SDK session explicitly disables environment proxy/netrc credential fallback and
redirects. Injected test-only netrc credentials are not transmitted. Parent environment
remains restricted. No owner auth or secrets are used. Server serializes POST acceptance
and lookup under fixture tenant lock and enforces the signed timestamp/window before
commit, preserving accepted-before-timeout authoritative truth.

Validation: initial7 deadline/SDK cases PASS (23.12s), repaired22 claim/expiry/native/SDK
cases PASS (66.83s), final20 fill/deadline/SDK cases PASS (111.11s). Final178 units,
strict mypy56/138 schemas/scan/offline SDK PASS; actual platform/ledger17 PASS (11.89s).
Complete final90 actual cases PASS (302.24s), wheel-sdist PASS. Earlier full
run89 passes plus one terminal-read timeout prompted bounded read repair. An earlier
mixed-custody event test was fixed to read its tenant rather than the first1000 global
pending events; production batch limit is preserved. One run was discarded after a
migration changed while it was active; no pass evidence is claimed from that run.
