# Domain Model V1

Rules: globally unique IDs, UTC timestamps, fixed-precision decimal financial values, tenant-aware core records, immutable promoted artifacts, append-only financial/audit history.

Core:
- Tenant / Owner.
- Agent: stable identity, type/status/provider/permission refs.
- AgentSkill: versioned typed capability.
- AgentMemoryRecord: provenance, type, content ref, confidence/quality, retention, supersession.
- ExperienceRecord: agent/portfolio/strategy/model refs, market/regime snapshots, entry/exit/risk/execution context, outcome/anomalies.
- AIProviderConfig: provider/model/effort/timeout/fallback; credential_ref only, never raw credential.
- Portfolio / CapitalAllocation.
- RiskProfileVersion: immutable LOW/MEDIUM/HIGH parameters and owner-cap refs.
- ExchangeAccount: environment, secret_ref, permission snapshot, status.
- Instrument: venue/symbol/assets/market type and precision/filter metadata.
- Strategy / StrategyVersion.
- Model / ModelVersion.
- Experiment.
- TradeIntent (see TRADE_INTENT.md).
- RiskDecision / PolicyDecision.
- Order / Fill / Position.
- LedgerTransaction / LedgerPosting: append-only, corrections via compensating transaction.
- Incident.
- AuditEvent.
- CertificationState.
- ProgramCheckpoint: development-only durable state (branch/commit/phase/next action/blocker/usage state), never trading authority.
