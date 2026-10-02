# Domain Model V1

## Design rules

- IDs are globally unique within the platform.
- Production strategy/model versions are immutable.
- Financial events are append-only.
- Important records are tenant-aware even in single-tenant mode.
- Timestamps are stored in UTC.
- Monetary values use fixed-precision decimal representations, never binary float for accounting.

## Core entities

### Tenant

Fields:

- tenant_id
- name
- status
- created_at

Enterprise Local uses one tenant.

### Owner

Fields:

- owner_id
- tenant_id
- identity metadata
- status

### Agent

Fields:

- agent_id
- tenant_id
- agent_type
- stable_name
- status
- provider_config_id
- permission_profile_id
- created_at

### AgentSkill

Fields:

- skill_id
- version
- name
- input_schema
- output_schema
- required_permissions
- implementation_ref
- status

### AgentMemoryRecord

Fields:

- memory_id
- agent_id
- memory_type
- content_ref
- source_ref
- confidence
- created_at
- supersedes_id
- retention_class

### Portfolio

Fields:

- portfolio_id
- tenant_id
- name
- mode
- risk_profile
- status
- base_currency

### CapitalAllocation

Fields:

- allocation_id
- portfolio_id
- source
- amount
- effective_at
- reason
- approved_by

### ExchangeAccount

Fields:

- exchange_account_id
- tenant_id
- exchange
- environment
- secret_ref
- permissions_snapshot
- status

Never store raw API secrets here.

### Instrument

Fields:

- instrument_id
- venue
- symbol
- base_asset
- quote_asset
- market_type
- status

### Strategy

Fields:

- strategy_id
- name
- strategy_family
- status

### StrategyVersion

Fields:

- strategy_version_id
- strategy_id
- semantic_version
- artifact_ref
- config_hash
- lifecycle_stage
- created_at
- immutable_after_promotion

### Model

Fields:

- model_id
- name
- model_family

### ModelVersion

Fields:

- model_version_id
- model_id
- artifact_ref
- dataset_version
- feature_set_version
- metrics
- lifecycle_stage
- created_at

### Experiment

Fields:

- experiment_id
- hypothesis_id
- dataset_ref
- config
- artifact_refs
- metrics
- result
- created_at

### TradeIntent

Defined in TRADE_INTENT.md.

### RiskDecision

Fields:

- risk_decision_id
- intent_id
- decision
- reason_codes
- calculated_exposure
- drawdown_state
- market_health
- reconciliation_health
- ruleset_version
- created_at

### PolicyDecision

Fields:

- policy_decision_id
- intent_id
- actor_id
- decision
- reason_codes
- policy_bundle_version
- created_at

### Order

Fields:

- order_id
- intent_id
- venue_order_id
- client_order_id
- state
- symbol
- side
- order_type
- requested_quantity
- filled_quantity
- limit_price
- average_fill_price
- created_at
- updated_at

### Fill

Fields:

- fill_id
- order_id
- venue_fill_id
- quantity
- price
- fee_amount
- fee_asset
- timestamp

### Position

For Spot V1 this represents platform-owned inventory/exposure attribution.

Fields:

- position_id
- portfolio_id
- instrument_id
- quantity
- cost_basis
- unrealized_pnl
- realized_pnl
- updated_at

### LedgerEntry

Fields:

- ledger_entry_id
- tenant_id
- portfolio_id
- entry_type
- asset
- amount
- related_order_id
- related_fill_id
- reason
- timestamp
- correction_of_id

Ledger entries are append-only.

### Incident

Fields:

- incident_id
- severity
- category
- status
- trigger_event_id
- summary
- opened_at
- closed_at

### AuditEvent

Fields:

- audit_event_id
- actor_id
- action
- resource_type
- resource_id
- trace_id
- payload_ref
- timestamp

### CertificationState

Fields:

- tenant_id
- current_level
- achieved_at
- evidence_refs
- blockers
- last_reviewed_at
