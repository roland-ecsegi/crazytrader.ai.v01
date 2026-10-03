"""Internal immutable risk evidence and trusted state boundary.

No public/agent endpoint accepts RiskContext. A service publisher must match the
actual journal, market archive and owner configuration before contexts are stored.
Above-L0 certification requires a later verified registry, never a caller assertion.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.market import InstrumentMetadata, MarketTrade
from crazytrader_contracts.risk import (
    MarketSafetyFact,
    OperatingControls,
    OwnerRiskConfiguration,
    PolicyAuthorization,
    PortfolioSafetyFact,
    RiskAuthorization,
    RiskContext,
    RiskEvaluationRecord,
    VenueSafetyFact,
)
from crazytrader_ledger.store import LedgerStore
from crazytrader_market.archive import S3Artifacts
from crazytrader_market.monitor import TradeCheckpoint
from crazytrader_platform.storage import ConflictError, EventStore

from .engine import evaluate


class StateUnavailable(ValueError):
    """Missing, stale or unverified canonical state; no authorization granted."""


class RiskStore:
    def __init__(self, store: EventStore) -> None:
        self.store = store

    def install_owner_configuration(self, config: OwnerRiskConfiguration) -> None:
        """Owner-admin-only internal installation; never exposed as an agent tool."""
        config = OwnerRiskConfiguration.model_validate(config.model_dump())
        body = canonical(config)
        with self.store.connection() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("ledger:" + config.tenant_id,),
            )
            row = conn.execute(
                "SELECT digest FROM ct_risk_configs WHERE config_id=%s", (config.config_id,)
            ).fetchone()
            if row is not None and row["digest"] != digest(body):
                raise ConflictError("owner configuration version reused")
            conn.execute(
                "INSERT INTO ct_risk_configs(config_id,tenant_id,actor_id,digest,body) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (config.config_id, config.tenant_id, config.actor_id, digest(body), body),
            )
            conn.execute(
                "INSERT INTO ct_risk_active_configs(tenant_id,actor_id,config_id) VALUES(%s,%s,%s) "
                "ON CONFLICT(tenant_id,actor_id) DO UPDATE SET config_id=excluded.config_id",
                (config.tenant_id, config.actor_id, config.config_id),
            )

    def configuration(self, tenant: str, actor: str) -> OwnerRiskConfiguration:
        with self.store.connection() as conn:
            row = conn.execute(
                "SELECT c.body,c.digest FROM ct_risk_configs c JOIN ct_risk_active_configs a "
                "USING(tenant_id,actor_id,config_id) WHERE a.tenant_id=%s AND a.actor_id=%s",
                (tenant, actor),
            ).fetchone()
        if row is None:
            raise StateUnavailable("owner configuration/permission unavailable")
        config = OwnerRiskConfiguration.model_validate_json(str(row["body"]))
        if digest(canonical(config)) != row["digest"]:
            raise ConflictError("owner configuration integrity failure")
        return config

    def record_venue_fact(self, fact: VenueSafetyFact) -> None:
        """Reconciliation service publication; data-plane role only, not an agent tool."""
        fact = VenueSafetyFact.model_validate(fact.model_dump())
        body = canonical(fact)
        with self.store.connection() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("ledger:" + fact.tenant_id,),
            )
            inserted = conn.execute(
                "INSERT INTO ct_venue_safety_facts "
                "(digest,tenant_id,environment,execution_mode,body,observed_at) "
                "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING digest",
                (
                    digest(body),
                    fact.tenant_id,
                    fact.environment,
                    fact.execution_mode,
                    body,
                    fact.observed_at,
                ),
            ).fetchone()
            if inserted is None:
                existing = conn.execute(
                    "SELECT digest FROM ct_venue_safety_facts WHERE tenant_id=%s "
                    "AND environment=%s AND execution_mode=%s AND observed_at=%s",
                    (fact.tenant_id, fact.environment, fact.execution_mode, fact.observed_at),
                ).fetchone()
                if existing is None or existing["digest"] != digest(body):
                    raise ConflictError("venue source identity collision")

    def record_source_fact(
        self, fact: PortfolioSafetyFact | MarketSafetyFact | OperatingControls
    ) -> None:
        """Trusted service publication. Writers receive scoped SQL roles in security gate."""
        fact = type(fact).model_validate(fact.model_dump())
        resource = fact.symbol if isinstance(fact, MarketSafetyFact) else fact.portfolio_id
        observed = fact.occurred_at if isinstance(fact, OperatingControls) else fact.observed_at
        body = canonical(fact)
        with self.store.connection() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("ledger:" + fact.tenant_id,),
            )
            inserted = conn.execute(
                "INSERT INTO ct_risk_source_facts "
                "(digest,tenant_id,resource_id,source_service,schema_ref,body,observed_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING digest",
                (
                    digest(body),
                    fact.tenant_id,
                    resource,
                    fact.source_service,
                    type(fact).__name__ + ".v1",
                    body,
                    observed,
                ),
            ).fetchone()
            if inserted is None:
                existing = conn.execute(
                    "SELECT digest FROM ct_risk_source_facts WHERE tenant_id=%s "
                    "AND resource_id=%s AND schema_ref=%s AND observed_at=%s",
                    (fact.tenant_id, resource, type(fact).__name__ + ".v1", observed),
                ).fetchone()
                if existing is None or existing["digest"] != digest(body):
                    raise ConflictError("service fact identity collision")

    def source_fact(
        self,
        tenant: str,
        resource: str,
        model: type[PortfolioSafetyFact] | type[MarketSafetyFact] | type[OperatingControls],
    ) -> PortfolioSafetyFact | MarketSafetyFact | OperatingControls | None:
        with self.store.connection() as conn:
            row = conn.execute(
                "SELECT body,digest FROM ct_risk_source_facts "
                "WHERE tenant_id=%s AND resource_id=%s "
                "AND schema_ref=%s ORDER BY observed_at DESC LIMIT 1",
                (tenant, resource, model.__name__ + ".v1"),
            ).fetchone()
        if row is None:
            return None
        fact = model.model_validate_json(str(row["body"]))
        if digest(canonical(fact)) != row["digest"]:
            raise ConflictError("risk service fact integrity failure")
        return fact

    def validate_backbone(
        self, context: RiskContext, objects: S3Artifacts, now: datetime
    ) -> OwnerRiskConfiguration:
        context = RiskContext.model_validate(context.model_dump())
        config = self.configuration(context.tenant_id, context.actor_id)
        if (
            context.owner_limits,
            context.profile_limits,
            context.execution_mode,
            context.owner_live_activated,
            context.risk_profile_version_id,
            context.profile_name,
        ) != (
            config.owner_limits,
            config.profile_limits,
            config.execution_mode,
            config.owner_live_activated,
            config.risk_profile_version_id,
            config.profile_name,
        ):
            raise StateUnavailable("risk context does not match active owner configuration")
        if context.owner_reduction_authorized != ("risk.reduce" in config.actor_permissions):
            raise StateUnavailable("reduction permission assertion mismatch")
        # Current durable certification is L0; a later evidence verifier replaces this boundary.
        if context.certification.current_level != "L0":
            raise StateUnavailable("unverified certification assertion")
        if (
            context.strategy_version_id is not None
            or context.strategy_lifecycle is not None
            or context.model_version_ids
            or context.model_lifecycles
        ):
            raise StateUnavailable("lifecycle registry not yet verified")
        snapshot = LedgerStore(self.store).snapshot(
            context.tenant_id, context.portfolio.portfolio_id, context.portfolio.as_of
        )
        if snapshot != context.portfolio:
            raise StateUnavailable("risk portfolio differs from canonical journal")
        base = next((b for b in snapshot.balances if b.asset == context.metadata.base_asset), None)
        reserved = base.reserved if base else Decimal(0)
        if context.pending_sell_quantity != reserved:
            raise StateUnavailable("pending SELL quantity differs from journal reservations")
        with self.store.connection() as conn:
            row = conn.execute(
                "SELECT body,health,heartbeat_at FROM ct_market_checkpoints WHERE "
                "tenant_id=%s AND environment=%s AND symbol=%s",
                (context.tenant_id, context.metadata.environment, context.metadata.symbol),
            ).fetchone()
            if row is None:
                raise StateUnavailable("market checkpoint unavailable")
            checkpoint = TradeCheckpoint.model_validate_json(str(row["body"]))
            if checkpoint.metadata_version != context.metadata.metadata_version:
                raise StateUnavailable("market metadata version mismatch")
            if (
                context.market.last_trade_id,
                context.market.gap_target,
                context.market.last_exchange_at,
                context.market.last_received_at,
            ) != (
                checkpoint.last_id,
                checkpoint.gap_target,
                checkpoint.last_exchange_at,
                checkpoint.last_received_at,
            ):
                raise StateUnavailable("market checkpoint assertion mismatch")
            heartbeat = row["heartbeat_at"]
            if not isinstance(heartbeat, datetime):
                raise StateUnavailable("market heartbeat unavailable")
            age = timedelta(
                seconds=min(
                    config.owner_limits.state_max_age_seconds,
                    config.profile_limits.state_max_age_seconds,
                )
            )
            healthy = (
                row["health"] == "HEALTHY"
                and checkpoint.fresh_samples >= 2
                and not checkpoint.conflict
                and checkpoint.gap_target is None
                and timedelta(0) <= now - heartbeat <= age
            )
            if context.market.health == "HEALTHY" and not healthy:
                raise StateUnavailable("unverified healthy market assertion")
            trade_row = conn.execute(
                "SELECT body,digest FROM ct_market_records WHERE "
                "tenant_id=%s AND environment=%s AND symbol=%s AND trade_id=%s",
                (
                    context.tenant_id,
                    context.metadata.environment,
                    context.metadata.symbol,
                    checkpoint.last_id,
                ),
            ).fetchone()
            manifest = conn.execute(
                "SELECT s.object_key,s.digest FROM ct_market_sources s "
                "JOIN ct_market_batches b ON b.source_digest=s.digest WHERE s.tenant_id=%s "
                "AND s.environment=%s AND s.symbol=%s AND b.status='COMMITTED' "
                "ORDER BY s.created_at DESC LIMIT 1",
                (context.tenant_id, context.metadata.environment, context.metadata.symbol),
            ).fetchone()
            fact_row = conn.execute(
                "SELECT body,digest FROM ct_venue_safety_facts WHERE tenant_id=%s "
                "AND environment=%s AND execution_mode=%s ORDER BY observed_at DESC LIMIT 1",
                (context.tenant_id, context.metadata.environment, context.execution_mode),
            ).fetchone()
        if trade_row is None or manifest is None:
            raise StateUnavailable("market source/record unavailable")
        trade = MarketTrade.model_validate_json(str(trade_row["body"]))
        if digest(canonical(trade)) != trade_row["digest"] or context.price not in {
            None,
            trade.price,
        }:
            raise StateUnavailable("risk price differs from immutable market record")
        source_bytes = objects.client.get_object(
            Bucket=objects.bucket, Key=str(manifest["object_key"])
        )["Body"].read()
        if digest(source_bytes.decode()) != manifest["digest"]:
            raise ConflictError("market source object integrity failure")
        source = json.loads(source_bytes)
        metadata = InstrumentMetadata.model_validate(source["metadata"])
        if metadata != context.metadata:
            raise StateUnavailable("risk filters differ from archived venue metadata")
        if fact_row is None:
            if context.venue_health != "UNKNOWN" or context.reconciliation_health != "UNKNOWN":
                raise StateUnavailable("venue/reconciliation proof unavailable")
        else:
            fact = VenueSafetyFact.model_validate_json(str(fact_row["body"]))
            if (
                digest(canonical(fact)) != fact_row["digest"]
                or context.observed_at > fact.observed_at
                or not timedelta(0) <= now - fact.observed_at <= age
            ):
                raise StateUnavailable("venue/reconciliation proof stale or changed")
            if (fact.venue_health, fact.reconciliation_health) != (
                context.venue_health,
                context.reconciliation_health,
            ):
                raise StateUnavailable("venue/reconciliation assertion mismatch")
        history = LedgerStore(self.store).history(context.tenant_id)
        ledger_head = digest(
            json.dumps([digest(canonical(tx)) for tx in history], separators=(",", ":"))
        )
        portfolio_fact = self.source_fact(
            context.tenant_id, context.portfolio.portfolio_id, PortfolioSafetyFact
        )
        if isinstance(portfolio_fact, PortfolioSafetyFact):
            if (
                portfolio_fact.ledger_head_sha256 != ledger_head
                or context.observed_at > portfolio_fact.observed_at
                or portfolio_fact.mode != context.portfolio.mode
                or portfolio_fact.symbol != context.metadata.symbol
                or portfolio_fact.strategy_version_id != context.strategy_version_id
                or not timedelta(0) <= now - portfolio_fact.observed_at <= age
            ):
                raise StateUnavailable("portfolio safety source is stale or ledger changed")
            fields = (
                "accounting_health",
                "total_exposure",
                "mode_exposure",
                "portfolio_exposure",
                "strategy_exposure",
                "symbol_exposure",
                "active_positions",
                "orders_in_window",
                "window_started_at",
                "daily_loss",
                "drawdown",
            )
            if any(getattr(context, name) != getattr(portfolio_fact, name) for name in fields):
                raise StateUnavailable(
                    "portfolio safety assertion differs from canonical service fact"
                )
        else:
            raise StateUnavailable("portfolio safety provenance unavailable")
        market_fact = self.source_fact(context.tenant_id, context.metadata.symbol, MarketSafetyFact)
        if isinstance(market_fact, MarketSafetyFact):
            if (
                market_fact.metadata_version != context.metadata.metadata_version
                or context.observed_at > market_fact.observed_at
                or not timedelta(0) <= now - market_fact.observed_at <= age
            ):
                raise StateUnavailable("market safety source stale or metadata changed")
            if (context.liquidity, context.spread) != (market_fact.liquidity, market_fact.spread):
                raise StateUnavailable("liquidity/spread assertion differs from service fact")
        elif context.liquidity is not None or context.spread is not None:
            raise StateUnavailable("unverified liquidity/spread assertion")
        controls = self.source_fact(
            context.tenant_id, context.portfolio.portfolio_id, OperatingControls
        )
        if (
            not isinstance(controls, OperatingControls)
            or controls.occurred_at > now
            or controls.owner_authority_ref != config.owner_authority_ref
        ):
            raise StateUnavailable("owner operating controls unavailable")
        if (
            context.kill_scope,
            context.mode_enabled,
            context.portfolio_enabled,
            context.strategy_enabled,
        ) != (
            controls.kill_scope,
            controls.mode_enabled,
            controls.portfolio_enabled,
            controls.strategy_enabled,
        ):
            raise StateUnavailable("kill/pause assertion differs from owner controls")
        return config

    def publish_context(self, context: RiskContext, objects: S3Artifacts, now: datetime) -> None:
        context = RiskContext.model_validate(context.model_dump())
        config = self.validate_backbone(context, objects, now)
        body = canonical(context)
        with self.store.connection() as conn:
            existing = conn.execute(
                "SELECT digest FROM ct_risk_contexts WHERE context_id=%s", (context.context_id,)
            ).fetchone()
            if existing is not None and existing["digest"] != digest(body):
                raise ConflictError("context ID reused with changed state")
            conn.execute(
                "INSERT INTO ct_risk_contexts "
                "(context_id,tenant_id,intent_digest,digest,body,config_id,observed_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    context.context_id,
                    context.tenant_id,
                    context.intent_sha256,
                    digest(body),
                    body,
                    config.config_id,
                    context.observed_at,
                ),
            )

    def context(self, tenant: str, actor: str, intent_hash: str) -> RiskContext:
        config = self.configuration(tenant, actor)
        with self.store.connection() as conn:
            row = conn.execute(
                "SELECT body,digest FROM ct_risk_contexts WHERE tenant_id=%s "
                "AND intent_digest=%s AND config_id=%s ORDER BY observed_at DESC LIMIT 1",
                (tenant, intent_hash, config.config_id),
            ).fetchone()
        if row is None:
            raise StateUnavailable("trusted risk context unavailable")
        context = RiskContext.model_validate_json(str(row["body"]))
        if digest(canonical(context)) != row["digest"] or context.actor_id != actor:
            raise ConflictError("risk context integrity/actor mismatch")
        return context

    def record(self, record: RiskEvaluationRecord) -> bool:
        record = RiskEvaluationRecord.model_validate(record.model_dump())
        if record.authorization != evaluate(
            record.intent, record.context, record.authorization.evaluated_at
        ):
            raise StateUnavailable("forged deterministic risk decision")
        intent_body, context_body, body = (
            canonical(record.intent),
            canonical(record.context),
            canonical(record),
        )
        with self.store.connection() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("risk-intent:" + record.intent.tenant_id + ":" + record.intent.intent_id,),
            )
            previous = conn.execute(
                "SELECT digest FROM ct_trade_intents WHERE intent_id=%s", (record.intent.intent_id,)
            ).fetchone()
            if previous is not None and previous["digest"] != digest(intent_body):
                raise ConflictError("intent ID reused with changed financial proposal")
            conn.execute(
                "INSERT INTO ct_trade_intents(intent_id,tenant_id,digest,body,created_at) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    record.intent.intent_id,
                    record.intent.tenant_id,
                    digest(intent_body),
                    intent_body,
                    record.intent.created_at,
                ),
            )
            existing = conn.execute(
                "SELECT record_digest FROM ct_risk_evaluations WHERE tenant_id=%s AND intent_id=%s",
                (record.intent.tenant_id, record.intent.intent_id),
            ).fetchone()
            if existing is not None and existing["record_digest"] != digest(body):
                raise ConflictError(
                    "terminal intent decision cannot be replaced; create a new intent"
                )
            inserted = conn.execute(
                "INSERT INTO ct_risk_evaluations "
                "(record_digest,tenant_id,intent_id,context_digest,risk_decision_id,body) "
                "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING record_digest",
                (
                    digest(body),
                    record.intent.tenant_id,
                    record.intent.intent_id,
                    digest(context_body),
                    record.authorization.decision.risk_decision_id,
                    body,
                ),
            ).fetchone()
            self._event(
                conn,
                record.authorization,
                "risk-engine",
                record.authorization.evaluated_at,
                "TradeIntentRiskApproved.v1"
                if record.authorization.decision.decision == "ALLOW"
                else "TradeIntentRiskDenied.v1",
            )
            if record.policy is not None:
                self._event(
                    conn,
                    record.policy,
                    "policy-engine",
                    record.policy.evaluated_at,
                    "TradeIntentPolicyApproved.v1"
                    if record.policy.decision.decision == "ALLOW"
                    else "TradeIntentPolicyDenied.v1",
                )
            return inserted is not None

    def _event(
        self,
        conn: psycopg.Connection[dict[str, object]],
        payload: RiskAuthorization | PolicyAuthorization,
        source: str,
        occurred: datetime,
        event_type: str,
    ) -> None:
        risk = payload if isinstance(payload, RiskAuthorization) else payload.risk_authorization
        fingerprint = digest(canonical(payload))
        event = EventEnvelope(
            event_id="decision:" + fingerprint,
            event_type=event_type,
            schema_version="1",
            occurred_at=occurred,
            tenant_id=risk.tenant_id,
            source_service=source,
            actor_id=risk.actor_id,
            trace_id="decision:" + fingerprint,
            correlation_id=risk.decision.intent_id,
            payload=PayloadReference(
                artifact_ref=fingerprint,
                sha256=fingerprint,
                payload_schema_ref=type(payload).__name__ + ".v1",
            ),
        )
        self.store.append_in_transaction(conn, event, payload)
