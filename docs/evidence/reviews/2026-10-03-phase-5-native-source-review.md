# Independent adversarial root pass: native source boundary

Separate root review after implementation, not human/separate-model approval.
Reviewed explicit simulation-only descriptors, native vs SDK provenance, immutable
job/request/order references, exact Decimal representation, quote fee/cash/clock
binding, credential-minimal subprocess and private claim/result fsync/recovery.

Repairs: exclusive durable claim prevents rerun after missing result; upstream
InstrumentId constructed from Symbol/Venue; full fixture price filter retained;
strict integer order count rejects bool; native event clock/currency/order type bound.
Four engine recovery/precision/cash tests PASS before three additional source identity
negative cases. Existing financial/SDK contracts unchanged. CI setup now restores
pinned reviewed unmodified native environment. No live transport configured.

No bounded source defect found. PostgreSQL request binding, durable financial/native
fill journal/state, incident containment and restart proofs remain explicit work.
No existing result absence is interpreted as exchange absence or permission to retry.
