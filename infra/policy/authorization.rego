package crazytrader.authorization

import rego.v1

intent := json.unmarshal(input.intent_json)
context := json.unmarshal(input.context_json)
authorization := input.authorization
now := time.parse_rfc3339_ns(input.now)

valid_binding if {
    input.schema_version == "1"
    input.policy_bundle_sha256 == data.bundle.policy_sha256
    crypto.sha256(input.intent_json) == authorization.intent_sha256
    crypto.sha256(input.context_json) == authorization.context_sha256
    authorization.tenant_id == intent.tenant_id
    authorization.tenant_id == context.tenant_id
    input.tenant_id == context.tenant_id
    input.actor_id == authorization.actor_id
    input.actor_id == context.actor_id
    authorization.decision.intent_id == intent.intent_id
    authorization.decision.decision == "ALLOW"
    now >= time.parse_rfc3339_ns(authorization.evaluated_at)
    now < time.parse_rfc3339_ns(authorization.expires_at)
    now >= time.parse_rfc3339_ns(intent.created_at)
    now < time.parse_rfc3339_ns(intent.expires_at)
    intent.symbol in input.symbol_allowlist
    intent.portfolio_id == context.portfolio.portfolio_id
    authorization.execution_mode == context.execution_mode
}

live_permitted if { context.execution_mode != "LIVE" }
live_permitted if {
    context.execution_mode == "LIVE"
    context.certification.current_level == "L6"
    context.owner_live_activated == true
    "live.activate" in input.actor_permissions
}

increasing_permitted if {
    authorization.decision.risk_effect == "RISK_INCREASING"
    intent.side == "BUY"
    "risk.increase" in input.actor_permissions
    context.kill_scope == "NONE"
    context.mode_enabled == true
    context.portfolio_enabled == true
    context.strategy_enabled == true
    context.market.health == "HEALTHY"
    context.venue_health == "HEALTHY"
    context.reconciliation_health == "HEALTHY"
    context.accounting_health == "HEALTHY"
}

reducing_permitted if {
    authorization.decision.risk_effect == "RISK_REDUCING"
    intent.side == "SELL"
    "risk.reduce" in input.actor_permissions
    context.owner_reduction_authorized == true
    context.kill_scope != "CANCEL_ONLY"
    context.venue_health == "HEALTHY"
    context.reconciliation_health == "HEALTHY"
    context.accounting_health == "HEALTHY"
}

allow if { valid_binding; live_permitted; increasing_permitted }
allow if { valid_binding; live_permitted; reducing_permitted }
default allow := false

reason_codes := ["POLICY_AUTHORIZED"] if allow
reason_codes := ["POLICY_DENIED"] if not allow

decision := {
    "allow": allow,
    "reason_codes": reason_codes,
    "policy_bundle_sha256": data.bundle.policy_sha256,
    "policy_version": data.bundle.version,
    "risk_decision_id": authorization.decision.risk_decision_id,
    "intent_sha256": authorization.intent_sha256,
    "context_sha256": authorization.context_sha256,
    "tenant_id": input.tenant_id,
    "actor_id": input.actor_id,
}
