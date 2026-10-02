# Execution and Reconciliation V1

## Principle

Only a fully authorized execution request may reach the exchange adapter.

## Execution state machine

CREATED
-> RISK_PENDING
-> AUTHORIZED
-> SUBMITTING
-> SUBMITTED
-> ACKNOWLEDGED
-> PARTIALLY_FILLED
-> FILLED

Other states:
- DENIED
- REJECTED
- CANCEL_PENDING
- CANCELLED
- EXPIRED
- UNKNOWN
- RECOVERY_REQUIRED

Transitions are explicit, idempotent and audited.

## Idempotency

Every exchange submission has a stable client order identifier. Duplicate event delivery or service restart must not create duplicate exposure.

A network timeout after submission is **UNKNOWN**, never "failed". Do not blindly retry.

## UNKNOWN recovery

1. mark UNKNOWN;
2. block related duplicate submission;
3. reconcile using client/venue IDs;
4. recover accepted order if present;
5. if absence is established and intent remains valid, create a controlled retry execution request;
6. audit every step.

## Partial fills

Reservations, position attribution and ledger postings update incrementally and idempotently. Cancellation accounts for already-filled quantity.

## Reconciliation

Compare internal and venue:
- balances;
- open/recent orders;
- fills;
- reservations;
- attributed holdings.

Critical mismatch blocks new/increased risk and opens incident. Safe cancellation/risk reduction remains available where policy permits.

## Restart recovery

On startup:
- restore durable order state;
- replay idempotent events;
- query venue for unresolved orders;
- reconcile balances/positions;
- refuse new risk until healthy.

## Venue rules

Validate symbol status, tick/step sizes, min quantity/notional and other relevant Binance filters immediately before submission using versioned/current metadata.

## Live credential boundary

Execution service obtains live credentials only from owner-local OpenBao/equivalent. Agents and Codex Cloud never receive them.
