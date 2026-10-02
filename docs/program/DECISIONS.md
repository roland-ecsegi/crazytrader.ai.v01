# Program Decisions

## 2026-10-02 — Full architecture audit

- Enterprise Local completion means **L6 LIVE CERTIFIED**, not merely code-complete.
- Codex Cloud never receives live Binance credentials or owner-local Claude authentication material.
- Math Mode authoritative live decisions remain quantitative/statistical.
- Risk controls distinguish risk-increasing from risk-reducing actions.
- No fixed monthly return/minimum trade count is a system success requirement.
- Autonomous phase gates use mandatory adversarial review but do not require routine human approval.
- An early open-source compatibility/license spike is mandatory before rebuilding mature infrastructure.
- Current Codex Goals auto-continue only while active/within budget; budget-limit auto-resume cannot be guaranteed by repository code, so the project uses durable checkpoint/resume protocol.
- Final live canary runs on the owner-controlled local deployment, not Codex Cloud.

## 2026-10-02 — Phase 0 tooling/contracts

Python 3.12 with uv 0.12.19 and hash-locked dependencies; Pydantic frozen/extra-forbidden V1 contracts. Financial strings reject binary floats/nonfinite/excess precision and ambiguous sizing. Evidence-backed event payload references prevent mutable opaque financial payloads; producer schemas/resolution follow in service phases. UI TypeScript tooling deferred to Phase 13; directories are explicit ownership reservations. Validation is not financial authority or certification evidence verification.
