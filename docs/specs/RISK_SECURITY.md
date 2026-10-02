# Risk and Security Specification V1

Hard Risk is deterministic and independent from Risk Analyst Agent.

Inputs: TradeIntent, risk direction, portfolio/allocation, P&L/drawdown, open orders, liquidity/spread/volatility, market/exchange/reconciliation health, certification, risk profile and owner absolute limits.

## Risk direction

RISK_INCREASING, RISK_REDUCING, RISK_NEUTRAL.

Unknown/degraded safety state denies new/increased risk by default but preserves safe cancellation and authorized exposure reduction/flattening where venue state permits. All degraded-mode actions are audited.

Hard rules cover portfolio/mode/strategy/symbol/total caps, concurrent positions, order notional/frequency, daily loss/drawdown, liquidity/spread/slippage, stale/gapped data, exchange/reconciliation health and certification.

Low/Medium/High alter sizing/selectivity/concentration/volatility tolerance only within owner/system maxima.

## OPA

Deny risk-increasing actions on invalid certification, permissions, symbol allowlist, lifecycle stage, hard-risk decision, reconciliation/exchange health, global state or expiry. Policy must explicitly model emergency risk reduction so "trading blocked" never accidentally means "cannot close."

## Kill switches

Pause Agent/Strategy/Portfolio/Math/Strategy Mode; Disable New Orders; Cancel Open Orders; Reduce Exposure; Global Kill. Global Kill works without Claude and has explicit cancel-only vs flatten-approved policy.

## Secrets and infrastructure

Use OpenBao/equivalent locally. Binance live read/trade only, withdraw disabled, IP allowlist preferred, separate test/live keys. Codex Cloud/LLM prompt/memory never receive live secrets.

External content is untrusted. Use structured tools, provenance-aware memory, permission immutability, redaction, shell/network/filesystem isolation and output schema validation.

Internal DB/OPA/OpenBao endpoints are not directly WAN-exposed. Use least-privilege service identities, pinned dependencies/lockfiles, vulnerability scanning, SBOM before live, artifact hashes/signatures where practical and separate environment configs.

Unknown safety state blocks **new risk**, not safe management of existing exposure.
