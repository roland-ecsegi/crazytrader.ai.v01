"""Durable execution coordination. Only prepared, reserved simulation sends can be claimed.

Official-SDK loopback submission/query/cancel and exact fixture settlement are verified.
Above-L0 registries, BUY cost buffers, full account reconciliation
and signed owner-local adapters remain explicit engineering work.
"""

import json
from datetime import datetime

import psycopg
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.execution import (
    TRANSITION_EVENTS,
    ExecutionRequest,
    ExecutionState,
    ExecutionTransition,
    VenueOrderObservation,
)
from crazytrader_contracts.ledger import Account
from crazytrader_contracts.models import OrderState
from crazytrader_contracts.risk import RiskEvaluationRecord, VenueSafetyFact
from crazytrader_ledger.commands import reserve_custody
from crazytrader_ledger.store import LedgerStore
from crazytrader_market.adapter import normalize_metadata
from crazytrader_market.archive import S3Artifacts
from crazytrader_market.rules import TradingRuleArchive, check_market_rules
from crazytrader_platform.storage import ConflictError, EventStore
from crazytrader_risk.store import RiskStore, StateUnavailable

from .state import initial, transition


class ExecutionStore:
    def __init__(self, store: EventStore, objects: S3Artifacts | None = None) -> None:
        self.store, self.objects = store, objects

    def _lock(self, conn: psycopg.Connection[dict[str, object]], tenant: str) -> None:
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("ledger:" + tenant,))

    def load(self, request_id: str) -> ExecutionState:
        with self.store.connection() as conn:
            return self._load(conn, request_id)

    def _load(self, conn: psycopg.Connection[dict[str, object]], request_id: str) -> ExecutionState:
        row = conn.execute(
            "SELECT t.body,t.digest FROM ct_execution_current c "
            "JOIN ct_execution_transitions t USING(transition_id) WHERE c.execution_request_id=%s",
            (request_id,),
        ).fetchone()
        if row is None:
            raise StateUnavailable("durable execution request unavailable")
        evidence = ExecutionTransition.model_validate_json(str(row["body"]))
        if digest(canonical(evidence)) != row["digest"]:
            raise ConflictError("execution history integrity failure")
        return evidence.resulting_state

    def _write(
        self, conn: psycopg.Connection[dict[str, object]], change: ExecutionTransition
    ) -> None:
        change = ExecutionTransition.model_validate(change.model_dump())
        body = canonical(change)
        conn.execute(
            "INSERT INTO ct_execution_transitions "
            "(transition_id,execution_request_id,revision,digest,body) VALUES(%s,%s,%s,%s,%s)",
            (
                change.transition_id,
                change.execution_request_id,
                change.resulting_state.revision,
                digest(body),
                body,
            ),
        )
        if change.previous_state is None:
            conn.execute(
                "INSERT INTO ct_execution_current "
                "(execution_request_id,transition_id,revision,state) "
                "VALUES(%s,%s,%s,%s)",
                (
                    change.execution_request_id,
                    change.transition_id,
                    change.resulting_state.revision,
                    change.resulting_state.state.value,
                ),
            )
        else:
            updated = conn.execute(
                "UPDATE ct_execution_current SET transition_id=%s,revision=%s,state=%s "
                "WHERE execution_request_id=%s AND revision=%s AND state=%s",
                (
                    change.transition_id,
                    change.resulting_state.revision,
                    change.resulting_state.state.value,
                    change.execution_request_id,
                    change.previous_revision,
                    change.previous_state.value,
                ),
            )
            if updated.rowcount != 1:
                raise ConflictError("execution predecessor changed")
        event = EventEnvelope(
            event_id="execution:" + digest(body),
            event_type=TRANSITION_EVENTS.get(
                change.resulting_state.state, "ExecutionPreparationChanged.v1"
            ),
            schema_version="1",
            occurred_at=change.occurred_at,
            tenant_id=change.tenant_id,
            actor_id=change.actor_id,
            source_service="execution",
            trace_id=change.transition_id,
            correlation_id=change.execution_request_id,
            payload=PayloadReference(
                artifact_ref=digest(body),
                sha256=digest(body),
                payload_schema_ref="ExecutionTransition.v1",
            ),
        )
        self.store.append_in_transaction(conn, event, change)

    def prepare(
        self, request: ExecutionRequest, objects: S3Artifacts, now: datetime
    ) -> ExecutionState:
        """Atomically prepare already policy-approved protective simulation."""
        request = ExecutionRequest.model_validate(request.model_dump())
        self.objects = objects
        state = initial(request)
        if (
            request.execution_mode != "SIMULATION"
            or request.side != "SELL"
            or request.order_type != "MARKET"
        ):
            raise StateUnavailable("execution mode/order path not yet verified")
        with self.store.connection() as conn:
            self._lock(conn, request.tenant_id)
            incident = conn.execute(
                "SELECT 1 FROM ct_reconciliation_incidents WHERE tenant_id=%s UNION ALL "
                "SELECT 1 FROM ct_account_reconciliation_reports WHERE tenant_id=%s "
                "AND blocks_new_risk LIMIT 1",
                (request.tenant_id, request.tenant_id),
            ).fetchone()
            if incident is not None:
                raise StateUnavailable("canonical reconciliation incident blocks unproven exposure")
            existing = conn.execute(
                "SELECT body FROM ct_execution_requests WHERE execution_request_id=%s",
                (request.execution_request_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["body"]) != canonical(request):
                    raise ConflictError("execution request ID content collision")
                return self._load(conn, request.execution_request_id)
            row = conn.execute(
                "SELECT body FROM ct_risk_evaluations WHERE record_digest=%s "
                "AND tenant_id=%s AND intent_id=%s",
                (request.risk_record_sha256, request.tenant_id, request.intent_id),
            ).fetchone()
            if row is None:
                raise StateUnavailable("persisted risk and policy evidence unavailable")
            record = RiskEvaluationRecord.model_validate_json(str(row["body"]))
            if digest(canonical(record)) != request.risk_record_sha256:
                raise ConflictError("persisted risk record changed")
            policy = record.policy
            risk = record.authorization
            if (
                policy is None
                or policy.decision.decision != "ALLOW"
                or risk.decision.decision != "ALLOW"
            ):
                raise StateUnavailable("execution requires full approved risk and policy")
            if (
                request.intent_sha256,
                request.actor_id,
                request.portfolio_id,
                request.symbol,
                request.quantity,
                request.metadata_version,
                request.policy_bundle_sha256,
                request.expires_at,
            ) != (
                risk.intent_sha256,
                risk.actor_id,
                record.intent.portfolio_id,
                record.intent.symbol,
                risk.quantity,
                record.context.metadata.metadata_version,
                policy.policy_bundle_sha256,
                min(risk.expires_at, policy.expires_at, record.intent.expires_at),
            ):
                raise StateUnavailable("execution request differs from exact approved evidence")
            if (
                not max(risk.evaluated_at, policy.evaluated_at, request.created_at)
                <= now
                < request.expires_at
            ):
                raise StateUnavailable("execution approval expired or future")
            config = RiskStore(self.store).validate_backbone(record.context, objects, now)
            if (
                config.config_id != request.owner_config_id
                or config.policy_bundle_sha256 != request.policy_bundle_sha256
            ):
                raise StateUnavailable("owner approval configuration changed")
            if (
                request.environment != record.context.metadata.environment
                or request.side != record.intent.side
            ):
                raise StateUnavailable("venue or order direction changed")
            if request.execution_mode != record.context.execution_mode:
                raise StateUnavailable("execution mode changed")
            venue_row = conn.execute(
                "SELECT body FROM ct_venue_safety_facts WHERE tenant_id=%s "
                "AND environment=%s AND execution_mode=%s ORDER BY observed_at DESC LIMIT 1",
                (request.tenant_id, request.environment, request.execution_mode),
            ).fetchone()
            if (
                venue_row is None
                or VenueSafetyFact.model_validate_json(str(venue_row["body"])).venue_account_ref
                != request.venue_account_ref
            ):
                raise StateUnavailable("execution venue account differs from trusted proof")
            venue_rules_digest = self._venue_rules(conn, request, now)
            # Hold checkpoint row against concurrent stream mutation until reservation commits.
            conn.execute(
                "SELECT tenant_id FROM ct_market_checkpoints WHERE tenant_id=%s "
                "AND environment=%s AND symbol=%s FOR SHARE",
                (request.tenant_id, request.environment, request.symbol),
            )
            # Final validation after acquiring the row lock, with all safety/config writers
            # serialized by the same tenant journal lock. No durable state before this point.
            RiskStore(self.store).validate_backbone(record.context, objects, now)
            conn.execute(
                "INSERT INTO ct_execution_requests "
                "(execution_request_id,tenant_id,intent_id,order_id,venue_account_ref,"
                "client_order_id,risk_record_digest,digest,body) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    request.execution_request_id,
                    request.tenant_id,
                    request.intent_id,
                    request.order_id,
                    request.venue_account_ref,
                    request.client_order_id,
                    request.risk_record_sha256,
                    digest(canonical(request)),
                    canonical(request),
                ),
            )
            change = ExecutionTransition(
                transition_id="transition:" + digest(canonical(state)),
                tenant_id=request.tenant_id,
                actor_id=request.actor_id,
                execution_request_id=request.execution_request_id,
                order_id=request.order_id,
                client_order_id=request.client_order_id,
                previous_state=None,
                previous_revision=None,
                resulting_state=state,
                reason_code="DURABLE_REQUEST_CREATED",
                evidence_ref=request.risk_record_sha256,
                occurred_at=request.created_at,
            )
            self._write(conn, change)
            pending = transition(
                state,
                OrderState.RISK_PENDING,
                now,
                "APPROVED_EVIDENCE_LOADED",
                request.risk_record_sha256,
            )
            self._write(conn, pending)
            snapshot = record.context.portfolio
            asset = record.context.metadata.base_asset
            balance = next(b for b in snapshot.balances if b.asset == asset)
            # Canonical postings retain both original custody sources. The legacy
            # reserve_account column is a compatibility hint, never release authority.
            account: Account = "INVENTORY" if balance.inventory else "AVAILABLE"
            tx = reserve_custody(
                "reserve:" + request.execution_request_id,
                request.tenant_id,
                "reserve-source:" + request.execution_request_id,
                request.actor_id,
                request.risk_record_sha256,
                now,
                request.portfolio_id,
                asset,
                request.quantity,
                request.order_id,
                balance.inventory,
                balance.available,
            )
            LedgerStore(self.store).append_in_transaction(conn, tx)
            conn.execute(
                "INSERT INTO ct_execution_reservations "
                "(execution_request_id,reservation_tx_id,reserve_asset,reserve_account,reserve_amount,"
                "ledger_head_sha256,safety_sha256,checkpoint_sha256,venue_rules_digest) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    request.execution_request_id,
                    tx.transaction_id,
                    asset,
                    account,
                    request.quantity,
                    self._journal_head(conn, request.tenant_id),
                    self._safety(conn, request.tenant_id),
                    self._checkpoint(conn, request),
                    venue_rules_digest,
                ),
            )
            authorized = transition(
                pending.resulting_state,
                OrderState.AUTHORIZED,
                now,
                "POLICY_APPROVED_FUNDS_RESERVED",
                tx.transaction_id,
            )
            self._write(conn, authorized)
            return authorized.resulting_state

    def _journal_head(self, conn: psycopg.Connection[dict[str, object]], tenant: str) -> str:
        rows = conn.execute(
            "SELECT digest FROM ct_ledger_transactions WHERE tenant_id=%s "
            "ORDER BY recorded_at,transaction_id",
            (tenant,),
        ).fetchall()
        return digest(json.dumps([str(row["digest"]) for row in rows], separators=(",", ":")))

    def _safety(self, conn: psycopg.Connection[dict[str, object]], tenant: str) -> str:
        # Conservative: any owner/safety update invalidates the prepared send.
        rows = conn.execute(
            "SELECT digest FROM ct_risk_source_facts WHERE tenant_id=%s UNION ALL "
            "SELECT digest FROM ct_venue_safety_facts WHERE tenant_id=%s UNION ALL "
            "SELECT digest FROM ct_venue_rule_receipts WHERE tenant_id=%s UNION ALL "
            "SELECT encode(sha256(convert_to(body,'UTF8')),'hex') digest "
            "FROM ct_reconciliation_incidents WHERE tenant_id=%s UNION ALL "
            "SELECT digest FROM ct_account_reconciliation_reports WHERE tenant_id=%s "
            "AND blocks_new_risk ORDER BY digest",
            (tenant, tenant, tenant, tenant, tenant),
        ).fetchall()
        return digest(json.dumps([str(row["digest"]) for row in rows], separators=(",", ":")))

    def _checkpoint(
        self, conn: psycopg.Connection[dict[str, object]], request: ExecutionRequest
    ) -> str:
        row = conn.execute(
            "SELECT body FROM ct_market_checkpoints WHERE tenant_id=%s AND environment=%s "
            "AND symbol=%s FOR SHARE",
            (request.tenant_id, request.environment, request.symbol),
        ).fetchone()
        if row is None:
            raise StateUnavailable("final market checkpoint missing")
        return digest(str(row["body"]))

    def _venue_rules(
        self, conn: psycopg.Connection[dict[str, object]], request: ExecutionRequest, now: datetime
    ) -> str:
        if self.objects is None:
            raise StateUnavailable("venue rules source store must be configured after restart")
        try:
            receipt = TradingRuleArchive(self.store, self.objects).latest(
                request.tenant_id, request.environment, request.symbol, now
            )
            row = conn.execute(
                "SELECT body FROM ct_risk_evaluations WHERE record_digest=%s",
                (request.risk_record_sha256,),
            ).fetchone()
            if row is None:
                raise StateUnavailable("approved venue reference proof unavailable")
            record = RiskEvaluationRecord.model_validate_json(str(row["body"]))
            if digest(canonical(record)) != request.risk_record_sha256:
                raise ConflictError("approved venue reference integrity failure")
            metadata = normalize_metadata(
                receipt.rules.symbol_record(), request.environment, receipt.rules.observed_at
            )
            if (
                metadata.model_dump(exclude={"observed_at"})
                != record.context.metadata.model_dump(exclude={"observed_at"})
                or receipt.rules.metadata_version != request.metadata_version
            ):
                raise StateUnavailable("full venue rules differ from approved metadata")
            prices = {} if record.context.price is None else {0: record.context.price}
            reasons = check_market_rules(
                receipt.rules,
                request.side,
                request.quantity,
                now,
                reference_prices=prices,
                reference_observed_at=record.context.market.last_received_at
                or record.context.observed_at,
            )
            if reasons:
                raise StateUnavailable("full venue MARKET rule check denied")
            return digest(canonical(receipt))
        except (ValueError, ConflictError):
            raise StateUnavailable("full venue rules unavailable, changed or denied") from None

    def claim_submission(self, request_id: str, now: datetime) -> ExecutionState | None:
        """Return a single fenced claim. Already-started send never grants another claim."""
        current = self.load(request_id)
        request = current.request
        with self.store.connection() as conn:
            self._lock(conn, request.tenant_id)
            current = self._load(conn, request_id)
            if current.state != OrderState.AUTHORIZED:
                return None
            if request.execution_mode != "SIMULATION":
                raise StateUnavailable("signed transport is not enabled")
            proof = conn.execute(
                "SELECT * FROM ct_execution_reservations WHERE execution_request_id=%s",
                (request_id,),
            ).fetchone()
            if proof is None:
                raise StateUnavailable("submission reservation missing")
            config = RiskStore(self.store).configuration(request.tenant_id, request.actor_id)
            if config.config_id != request.owner_config_id:
                raise StateUnavailable("submission owner configuration changed")
            if (
                proof["ledger_head_sha256"],
                proof["safety_sha256"],
                proof["checkpoint_sha256"],
            ) != (
                self._journal_head(conn, request.tenant_id),
                self._safety(conn, request.tenant_id),
                self._checkpoint(conn, request),
            ):
                raise StateUnavailable("state changed after authorization/reservation")
            if self._venue_rules(conn, request, now) != proof["venue_rules_digest"]:
                raise StateUnavailable("full venue rules changed after reservation")
            change = transition(
                current,
                OrderState.SUBMITTING,
                now,
                "SINGLE_DURABLE_SUBMISSION_CLAIM",
                str(proof["reservation_tx_id"]),
            )
            self._write(conn, change)
            return change.resulting_state

    def recover_interrupted_submission(self, request_id: str, now: datetime) -> ExecutionState:
        """Startup cannot know whether a persisted SUBMITTING send reached the venue."""
        current = self.load(request_id)
        with self.store.connection() as conn:
            self._lock(conn, current.request.tenant_id)
            current = self._load(conn, request_id)
            if current.state != OrderState.SUBMITTING:
                return current
            unknown = transition(
                current,
                OrderState.UNKNOWN,
                now,
                "PROCESS_INTERRUPTED_DURING_SUBMISSION",
                "startup:" + request_id,
            )
            self._write(conn, unknown)
            return unknown.resulting_state

    def record_submission(self, observation: VenueOrderObservation) -> ExecutionState:
        """Fixture-only observation after the single send; fill settlement is separate."""
        observation = VenueOrderObservation.model_validate(observation.model_dump())
        current = self.load(observation.execution_request_id)
        request = current.request
        if request.execution_mode != "SIMULATION" or observation.action != "SUBMIT":
            raise StateUnavailable("fixture submission observation scope mismatch")
        if (
            observation.tenant_id,
            observation.venue_account_ref,
            observation.request_sha256,
            observation.client_order_id,
            observation.symbol,
            observation.side,
            observation.requested_quantity,
        ) != (
            request.tenant_id,
            request.venue_account_ref,
            digest(canonical(request)),
            request.client_order_id,
            request.symbol,
            request.side,
            request.quantity,
        ):
            raise StateUnavailable("submission observation ownership/identity mismatch")
        body = canonical(observation)
        with self.store.connection() as conn:
            self._lock(conn, request.tenant_id)
            current = self._load(conn, request.execution_request_id)
            existing = conn.execute(
                "SELECT body FROM ct_execution_observations WHERE digest=%s", (digest(body),)
            ).fetchone()
            if existing is not None:
                if str(existing["body"]) != body:
                    raise ConflictError("submission observation hash collision")
                return current
            if current.state != OrderState.SUBMITTING:
                raise StateUnavailable("submission outcome requires outstanding single claim")
            conn.execute(
                "INSERT INTO ct_execution_observations "
                "(digest,execution_request_id,body,observed_at) VALUES(%s,%s,%s,%s)",
                (digest(body), request.execution_request_id, body, observation.observed_at),
            )
            # A fill/cancel/reject in the first response still needs canonical settlement;
            # record truth but retain reservation and require reconciliation in this increment.
            target = (
                OrderState.SUBMITTED
                if observation.status == "NEW" and observation.filled_quantity == 0
                else OrderState.UNKNOWN
            )
            change = transition(
                current,
                target,
                observation.observed_at,
                "VENUE_ACK_RECEIVED"
                if target == OrderState.SUBMITTED
                else "AMBIGUOUS_OR_UNSETTLED_SUBMISSION",
                "observation:" + digest(body),
                venue_id=observation.venue_order_id,
            )
            self._write(conn, change)
            return change.resulting_state

    def start_recovery(self, request_id: str, now: datetime) -> ExecutionState:
        """Recover unresolved sends via query only. No path back to SUBMITTING."""
        current = self.load(request_id)
        with self.store.connection() as conn:
            self._lock(conn, current.request.tenant_id)
            current = self._load(conn, request_id)
            if current.state in {OrderState.SUBMITTING, OrderState.SUBMITTED}:
                unknown = transition(
                    current,
                    OrderState.UNKNOWN,
                    now,
                    "RECONCILE_UNRESOLVED_SUBMISSION",
                    "recovery:" + request_id,
                )
                self._write(conn, unknown)
                current = unknown.resulting_state
            if current.state == OrderState.UNKNOWN:
                recovery = transition(
                    current,
                    OrderState.RECOVERY_REQUIRED,
                    now,
                    "QUERY_STABLE_CLIENT_ID",
                    "recovery:" + request_id,
                )
                self._write(conn, recovery)
                return recovery.resulting_state
            return current

    def recover_open_order(self, observation: VenueOrderObservation) -> ExecutionState:
        """Only a query-proven unfilled open fixture order; no inferred settlement/absence."""
        observation = VenueOrderObservation.model_validate(observation.model_dump())
        current = self.load(observation.execution_request_id)
        request = current.request
        if request.execution_mode != "SIMULATION" or observation.action != "QUERY":
            raise StateUnavailable("fixture recovery observation scope mismatch")
        if (
            observation.tenant_id,
            observation.venue_account_ref,
            observation.request_sha256,
            observation.client_order_id,
            observation.symbol,
            observation.side,
            observation.requested_quantity,
        ) != (
            request.tenant_id,
            request.venue_account_ref,
            digest(canonical(request)),
            request.client_order_id,
            request.symbol,
            request.side,
            request.quantity,
        ):
            raise StateUnavailable("recovery observation ownership/identity mismatch")
        body = canonical(observation)
        with self.store.connection() as conn:
            self._lock(conn, request.tenant_id)
            current = self._load(conn, request.execution_request_id)
            conn.execute(
                "INSERT INTO ct_execution_observations "
                "(digest,execution_request_id,body,observed_at) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (digest(body), request.execution_request_id, body, observation.observed_at),
            )
            if current.state != OrderState.RECOVERY_REQUIRED:
                # Replay cannot repeat transitions or infer a second send.
                return current
            if (
                observation.status != "NEW"
                or observation.filled_quantity != 0
                or current.filled_quantity != 0
            ):
                # Persist actual known truth, keep unresolved and funds reserved. The next
                # accounting increment records/settles full fill evidence and incidents.
                return current
            change = transition(
                current,
                OrderState.ACKNOWLEDGED,
                observation.observed_at,
                "QUERY_PROVED_EXISTING_OPEN_ORDER",
                "reconciliation:" + digest(body),
                venue_id=observation.venue_order_id,
            )
            self._write(conn, change)
            return change.resulting_state
