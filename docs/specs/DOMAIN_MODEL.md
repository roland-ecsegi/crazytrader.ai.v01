# Domain Model V1

## Design rules

- Globally unique IDs.
- UTC timestamps.
- Fixed-precision decimal values for all financial/accounting calculations.
- Tenant-aware ownership fields where low-cost, even though Enterprise Local has one tenant.
- Promoted strategy/model versions are immutable.
- Ledger/audit history is append-only.
- External credentials are referenced, never stored raw in domain records.

## Tenant

Fields: tenant_id, name, status, created_at.

Enterprise Local uses one tenant.

## Owner

Fields: owner_id, tenant_id, identity_metadata, status, created_at.

## Agent

Fields:
- agent_id
- tenant_id
- agent_type
- stable_name
- status
- provider_config_id
- permission_profile_id
- memory_policy_id
- created_at
- updated_at

## AgentSkill

Fields:
- skill_id
- version
- name
- input_schema
- output_schema
- required_permissions
- implementation_ref
- resource_limits
- audit_category
- status

## AgentMemoryRecord

Fields:
- memory_id
- agent_id
- memory_type
- content_ref
- source_refs/provenance
- confidence_or_quality
- retention_class
- created_at
- supersedes_id
- validation_status

## ExperienceRecord

Fields:
- experience_id
- tenant_id
- agent_id
- portfolio_id
- strategy_version_id
- model_version_ids
- market_state_ref
- regime_ref
- entry_reason_ref
- exit_reason_ref
- risk_state_ref
- execution_quality_ref
- outcome_metrics
- anomaly_refs
- created_at

## AIProviderConfig

Fields:
- provider_config_id
- tenant_id
- provider_type
- model_policy
- effort_or_reasoning_policy
- timeout_policy
- fallback_policy
- credential_ref
- status

credential_ref points to owner-local secret/auth integration where needed; never raw credentials.

## Portfolio

Fields:
- portfolio_id
- tenant_id
- name
- mode: MATH | STRATEGY | RESERVE
- risk_profile_version_id where applicable
- status
- base_currency
- created_at

## CapitalAllocation

Fields:
- allocation_id
- portfolio_id
- source
- amount
- effective_at
- reason
- approved_by
- hard_cap_ref

## RiskProfileVersion

Fields:
- risk_profile_version_id
- profile_name: LOW | MEDIUM | HIGH
- immutable_parameters
- owner_absolute_limit_refs
- lifecycle_status
- created_at

## ExchangeAccount

Fields:
- exchange_account_id
- tenant_id
- exchange
- environment
- secret_ref
- permission_snapshot
- IP_allowlist_status
- status

Raw API secret never lives here.

## Instrument

Fields:
- instrument_id
- venue
- symbol
- base_asset
- quote_asset
- market_type
- quantity_precision
- price_precision
- min_quantity
- min_notional
- status
- venue_metadata_version

## Strategy / StrategyVersion

Strategy: strategy_id, name, strategy_family, status.

StrategyVersion:
- strategy_version_id
- strategy_id
- semantic_version
- artifact_ref
- config_hash
- lifecycle_stage
- validation_evidence_refs
- created_at
- immutable_after_promotion

## Model / ModelVersion

Model: model_id, name, model_family.

ModelVersion:
- model_version_id
- model_id
- artifact_ref
- dataset_version
- feature_set_version
- training_config_hash
- metrics
- lifecycle_stage
- validation_evidence_refs
- created_at

## Experiment

Fields:
- experiment_id
- hypothesis_id
- dataset_ref
- feature_set_ref
- config
- artifact_refs
- metrics
- result
- reproducibility_hash
- created_at

## TradeIntent

Defined in TRADE_INTENT.md.

## RiskDecision

Fields:
- risk_decision_id
- intent_id
- decision
- risk_effect
- reason_codes
- calculated_exposure
- drawdown_state
- market_health
- reconciliation_health
- ruleset_version
- created_at

## PolicyDecision

Fields:
- policy_decision_id
- intent_id
- actor_id
- decision
- reason_codes
- policy_bundle_version
- created_at

## Order

Fields:
- order_id
- intent_id
- execution_request_id
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

## Fill

Fields:
- fill_id
- order_id
- venue_fill_id
- quantity
- price
- fee_amount
- fee_asset
- timestamp

## Position

For Spot V1, represents platform-attributed inventory/exposure.

Fields:
- position_id
- portfolio_id
- instrument_id
- quantity
- cost_basis
- unrealized_pnl
- realized_pnl
- updated_at

## LedgerTransaction / LedgerPosting

LedgerTransaction:
- transaction_id
- tenant_id
- portfolio_id
- transaction_type
- reason
- related_order_id/fill_id
- correction_of_id
- timestamp

LedgerPosting:
- posting_id
- transaction_id
- account
- asset
- amount
- valuation_ref where required

Append-only. Corrections are compensating transactions.

## Incident

incident_id, severity, category, status, trigger_event_id, summary, opened_at, closed_at.

## AuditEvent

audit_event_id, actor_id, action, resource_type, resource_id, trace_id, payload_ref, timestamp.

## CertificationState

tenant_id, current_level, achieved_at, evidence_refs, blockers, last_reviewed_at.

## ProgramCheckpoint

Development/control-plane only:
- program_id
- working_branch
- last_durable_commit
- current_phase
- next_action
- blocker_state
- usage_state
- updated_at

ProgramCheckpoint never becomes a trading authority.
