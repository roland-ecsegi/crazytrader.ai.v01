"""Real archived market/journal risk boundary, immutable evidence and denial audit."""

import json
import os
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from botocore.exceptions import ClientError
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.models import Portfolio
from crazytrader_contracts.risk import (
    MarketSafetyFact,
    OperatingControls,
    OwnerRiskConfiguration,
    PortfolioSafetyFact,
    RiskContext,
    RiskEvaluationRecord,
    VenueSafetyFact,
)
from crazytrader_ledger.commands import move
from crazytrader_ledger.store import LedgerStore
from crazytrader_market.adapter import PublicMarketClient, normalize_metadata
from crazytrader_market.archive import AnalyticalTrades, HistoricalIngestor, S3Artifacts
from crazytrader_market.rules import TradingRuleArchive, capture_rules
from crazytrader_market.worker import MarketWorker
from crazytrader_platform.storage import ConflictError, EventStore
from crazytrader_risk.engine import evaluate
from crazytrader_risk.policy import OPAClient
from crazytrader_risk.service import RiskService
from crazytrader_risk.store import RiskStore, StateUnavailable

from tests.risk.test_engine import fixture
from tests.test_venue_rules import exchange_info

pytestmark = pytest.mark.skipif(not os.getenv("CT_TEST_S3"), reason="actual market stores required")


@pytest.fixture
def backbone():
    now = datetime.now(UTC)
    tenant = "risk:" + uuid.uuid4().hex
    store = EventStore(os.environ["CT_TEST_DSN"])
    for path in sorted(Path("infra/migrations").glob("*.sql")):
        store.migrate(path)
    objects = S3Artifacts(os.environ["CT_TEST_S3"], "market-fixture", "fixture", "fixture")
    try:
        objects.client.head_bucket(Bucket=objects.bucket)
    except ClientError as exc:
        if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
            raise
        objects.client.create_bucket(Bucket=objects.bucket)
    port = (
        subprocess.run(
            [
                "docker",
                "--host=unix:///var/run/docker.sock",
                "port",
                os.environ["CT_TEST_CH_CONTAINER"],
                "8123/tcp",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .rsplit(":", 1)[1]
    )
    analytics = AnalyticalTrades("127.0.0.1", int(port), "fixture", "fixture")
    analytics.migrate()
    intent, original = fixture("SELL")
    intent = type(intent).model_validate(
        intent.model_dump()
        | {
            "intent_id": tenant + ":intent",
            "tenant_id": tenant,
            "portfolio_id": tenant + ":math",
            "created_at": now,
            "expires_at": now + timedelta(seconds=30),
        }
    )
    full_rules = exchange_info()
    full_rules["symbols"][0]["filters"].insert(
        2,
        {
            "filterType": "PRICE_FILTER",
            "minPrice": "0",
            "maxPrice": "1000000",
            "tickSize": "0.01",
        },
    )
    # This fixture venue explicitly uses current trade price (window0), never a fabricated average.
    full_rules["symbols"][0]["filters"][-1]["avgPriceMins"] = 0
    metadata = normalize_metadata(full_rules["symbols"][0], "SANDBOX", now)
    TradingRuleArchive(store, objects).persist(
        tenant, capture_rules(full_rules, "BTCUSDT", "SANDBOX", now)
    )
    delta = now - datetime(1970, 1, 1, tzinfo=UTC)
    milliseconds = delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds // 1000

    class FixtureRead(PublicMarketClient):
        def __init__(self):
            self.environment = "SANDBOX"

        def read(self, *args, **kwargs):
            return [{"a": i, "p": "100", "q": "0.1", "T": milliseconds, "m": False} for i in (1, 2)]

    worker = MarketWorker(
        tenant, metadata, FixtureRead(), HistoricalIngestor(store, objects, analytics), store
    )
    worker.poll(now)
    # Freeze fixture heartbeat at the same controlled clock, not a certification assertion.
    with store.connection() as conn:
        conn.execute(
            "UPDATE ct_market_checkpoints SET heartbeat_at=%s WHERE tenant_id=%s", (now, tenant)
        )
    ledger = LedgerStore(store)
    ledger.register(
        Portfolio(
            portfolio_id=intent.portfolio_id,
            tenant_id=tenant,
            name="fixture",
            mode="MATH",
            status="ACTIVE",
            base_currency="USDT",
            created_at=now,
        )
    )
    ledger.append(
        move(
            tenant + ":fund",
            tenant,
            tenant + ":fund-source",
            "owner",
            "fixture",
            now,
            intent.portfolio_id,
            "BTC",
            "1",
            "FUNDING",
        )
    )
    checkpoint = worker.monitor.checkpoint
    market = original.market.model_copy(
        update={
            "occurred_at": now,
            "metadata_version": metadata.metadata_version,
            "last_trade_id": checkpoint.last_id,
            "last_exchange_at": checkpoint.last_exchange_at,
            "last_received_at": checkpoint.last_received_at,
        }
    )
    context = RiskContext.model_validate(
        original.model_dump()
        | {
            "context_id": tenant + ":ctx",
            "tenant_id": tenant,
            "intent_sha256": digest(canonical(intent)),
            "portfolio": ledger.snapshot(tenant, intent.portfolio_id, now),
            "metadata": metadata,
            "market": market,
            "observed_at": now,
            "certification": original.certification.model_dump()
            | {
                "tenant_id": tenant,
                "current_level": "L0",
                "achieved_at": now,
                "last_reviewed_at": now,
            },
            "window_started_at": now - timedelta(seconds=60),
        }
    )
    risk = RiskStore(store)
    policy = OPAClient("http://127.0.0.1:1", Path("infra/policy/authorization.rego"))
    config = OwnerRiskConfiguration(
        config_id=tenant + ":cfg",
        tenant_id=tenant,
        actor_id="owner",
        owner_authority_ref="owner-local",
        owner_limits=context.owner_limits,
        profile_limits=context.profile_limits,
        risk_profile_version_id=None,
        profile_name=None,
        execution_mode="SIMULATION",
        symbol_allowlist=("BTCUSDT",),
        actor_permissions=("risk.reduce",),
        owner_live_activated=False,
        offline_protective_authorized=False,
        policy_bundle_sha256=policy.policy_hash,
    )
    risk.install_owner_configuration(config)
    risk.record_venue_fact(
        VenueSafetyFact(
            tenant_id=tenant,
            environment="SANDBOX",
            execution_mode="SIMULATION",
            venue_account_ref="fixture",
            venue_health="HEALTHY",
            reconciliation_health="HEALTHY",
            observed_at=now,
            evidence_ref="fixture",
        )
    )
    ledger_head = digest(
        json.dumps([digest(canonical(tx)) for tx in ledger.history(tenant)], separators=(",", ":"))
    )
    names = (
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
        "accounting_health",
    )
    risk.record_source_fact(
        PortfolioSafetyFact.model_validate(
            {name: getattr(context, name) for name in names}
            | {
                "tenant_id": tenant,
                "portfolio_id": intent.portfolio_id,
                "ledger_head_sha256": ledger_head,
                "mode": "MATH",
                "symbol": "BTCUSDT",
                "strategy_version_id": None,
                "observed_at": now,
                "evidence_ref": "fixture",
            }
        )
    )
    risk.record_source_fact(
        MarketSafetyFact(
            tenant_id=tenant,
            symbol="BTCUSDT",
            metadata_version=metadata.metadata_version,
            liquidity=context.liquidity,
            spread=context.spread,
            observed_at=now,
            evidence_ref="fixture",
        )
    )
    risk.record_source_fact(
        OperatingControls(
            control_version="controls.v1",
            tenant_id=tenant,
            portfolio_id=intent.portfolio_id,
            owner_authority_ref="owner-local",
            kill_scope="NONE",
            mode_enabled=True,
            portfolio_enabled=True,
            strategy_enabled=True,
            occurred_at=now,
        )
    )
    return risk, objects, intent, context, config, policy, now


def test_trusted_context_replay_audit_and_restart(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    risk.publish_context(context, objects, now)
    assert (
        RiskStore(EventStore(os.environ["CT_TEST_DSN"])).context(
            intent.tenant_id, "owner", digest(canonical(intent))
        )
        == context
    )
    authorization = evaluate(intent, context, now)
    assert authorization.decision.decision == "ALLOW"  # protective fixture, L0 never new risk
    denied_policy = policy.authorize(
        intent, context, authorization, now, config.actor_permissions, config.symbol_allowlist
    )
    assert denied_policy.decision.decision == "DENY"  # actual unreachable OPA
    record = RiskEvaluationRecord(
        intent=intent, context=context, authorization=authorization, policy=denied_policy
    )
    assert risk.record(record)
    assert not risk.record(record)
    later = evaluate(intent, context, now + timedelta(microseconds=1))
    with pytest.raises(ConflictError, match="terminal intent"):
        risk.record(
            RiskEvaluationRecord(intent=intent, context=context, authorization=later, policy=None)
        )
    events = [
        e
        for e in risk.store.pending(limit=1000)
        if e.tenant_id == intent.tenant_id and e.source_service in {"risk-engine", "policy-engine"}
    ]
    assert len(events) == 2
    for event in events:
        assert risk.store.consume_audit(event)
        assert not risk.store.consume_audit(event)
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_risk_evaluations WHERE tenant_id=%s", (intent.tenant_id,)
            ).fetchone()["n"]
            == 1
        )
        with pytest.raises(psycopg.Error, match="append-only"):
            conn.execute("DELETE FROM ct_risk_evaluations WHERE tenant_id=%s", (intent.tenant_id,))


@pytest.mark.parametrize(
    "change",
    [
        {"accounting_health": "UNKNOWN"},
        {"total_exposure": "0"},
        {"liquidity": "1"},
        {"kill_scope": "NEW_ORDERS"},
        {"pending_sell_quantity": "1"},
        {"price": "101"},
    ],
)
def test_forged_source_fields_deny(backbone, change):
    risk, objects, intent, context, config, policy, now = backbone
    changed = RiskContext.model_validate(context.model_dump() | change)
    with pytest.raises(StateUnavailable):
        risk.publish_context(changed, objects, now)


def test_certification_configuration_and_source_mutations_deny(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    forged = RiskContext.model_validate(
        context.model_dump()
        | {"certification": context.certification.model_dump() | {"current_level": "L6"}}
    )
    with pytest.raises(StateUnavailable, match="certification"):
        risk.publish_context(forged, objects, now)
    risk.publish_context(context, objects, now)
    with pytest.raises(ConflictError):
        risk.publish_context(
            context.model_copy(update={"budget_ref": "changed-budget"}),
            objects,
            now,
        )
    with pytest.raises(ConflictError):
        risk.install_owner_configuration(config.model_copy(update={"actor_permissions": ()}))
    risk.install_owner_configuration(
        config.model_copy(update={"config_id": config.config_id + ":2"})
    )
    with pytest.raises(StateUnavailable, match="context unavailable"):
        risk.context(intent.tenant_id, "owner", digest(canonical(intent)))
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_owner_config_activations WHERE tenant_id=%s",
                (intent.tenant_id,),
            ).fetchone()["n"]
            == 2
        )


def test_service_persists_boundary_denial_and_refuses_changed_journal(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    service = RiskService(risk, objects, policy, lambda: now)
    with pytest.raises(StateUnavailable):
        service.evaluate(intent, "other-actor")
    risk.publish_context(context, objects, now)
    record = service.evaluate(intent, "owner")
    assert record.policy.decision.decision == "DENY"
    LedgerStore(risk.store).append(
        move(
            intent.tenant_id + ":new",
            intent.tenant_id,
            intent.tenant_id + ":new-source",
            "owner",
            "fixture",
            now,
            intent.portfolio_id,
            "BTC",
            "1",
            "FUNDING",
        )
    )
    with pytest.raises(StateUnavailable):
        service.evaluate(intent, "owner")
    with risk.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM ct_events WHERE tenant_id=%s "
                "AND event_type='RiskDecisionDenied.v1'",
                (intent.tenant_id,),
            ).fetchone()["n"]
            == 2
        )


def test_same_time_source_conflict_and_stale_source_deny(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    fact = risk.source_fact(intent.tenant_id, intent.portfolio_id, OperatingControls)
    risk.record_source_fact(fact)
    with pytest.raises(ConflictError, match="identity collision"):
        risk.record_source_fact(fact.model_copy(update={"kill_scope": "NEW_ORDERS"}))
    with pytest.raises(StateUnavailable):
        risk.publish_context(context, objects, now + timedelta(seconds=6))


def test_context_cannot_refresh_older_safety_sources(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    with pytest.raises(StateUnavailable):
        risk.publish_context(
            context.model_copy(update={"observed_at": now + timedelta(microseconds=1)}),
            objects,
            now + timedelta(microseconds=1),
        )
