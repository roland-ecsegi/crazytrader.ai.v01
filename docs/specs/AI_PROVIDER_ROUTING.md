# AI Provider Routing V1

Permanent agent identity is independent of provider/model/transport.

    Agent -> AI Gateway
              |-> Claude CLI / claude -p
              |-> Claude Agent SDK
              |-> Claude API
              |-> future provider

## Enterprise Local

Provider/model are selectable from the custom application UI.

Claude CLI and Claude Agent SDK may use the owner's authenticated Claude subscription where Anthropic supports that usage. Treat this as current operational capability, not a permanent pricing guarantee; adapters must expose auth/usage-limit state cleanly.

Owner Claude login/session material stays local and is never copied to Codex Cloud, source control, frontend storage or agent memory.

### CLI adapter
Controlled workdir/process boundary, timeout/cancel, normalized structured output, tool allowlist, no inherited Binance/OpenBao live secrets by default, secret redaction and provider/model/latency/status audit.

### Agent SDK adapter
Preferred where it provides cleaner programmatic agent/tool control under supported auth. Keep behind our adapter so provider policy changes do not redefine permanent agents.

### API adapter
Optional in Enterprise Local; normal commercial/SaaS path later. Supports usage/cost accounting, timeout/retry, provider failure, model policy and future tenant attribution.

Fallback is explicit/audited and cannot duplicate financial actions. TradeIntent/execution idempotency remain outside AI Gateway.

Claude/provider availability is never required for hard risk, OPA, kill switch, reconciliation, duplicate-order prevention, deterministic protection or ledger integrity.

Codex Cloud tests these adapters with mocks/non-secret config. Owner-local auth validation is a later external integration step.
