"""Atomic canonical fill settlement; unposted venue truth is durable suspense/incident.

No new-order authority, no AI dependency, no invented fee valuations or balances.
"""

import json
from datetime import timedelta
from decimal import Decimal, localcontext
from typing import Literal

import psycopg
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.events import EventEnvelope, PayloadReference
from crazytrader_contracts.execution import (
    ExecutionIncident,
    ExecutionState,
    VenueFillBatch,
    VenueOrderObservation,
)
from crazytrader_contracts.ledger import Account
from crazytrader_contracts.models import OrderState
from crazytrader_contracts.risk import RiskEvaluationRecord
from crazytrader_ledger.commands import account_fill, move
from crazytrader_ledger.store import InsufficientFunds, LedgerStore
from crazytrader_platform.storage import ConflictError
from crazytrader_risk.store import StateUnavailable

from .state import ALLOWED, transition
from .store import ExecutionStore

Reason = Literal[
    "UNPROVEN_FILL_BATCH",
    "ACCOUNTING_ATTRIBUTION_FAILED",
    "FILL_ID_CONFLICT",
    "CUMULATIVE_MISMATCH",
    "TERMINAL_STATE_CONFLICT",
]


class FillSettlement:
    def __init__(self, execution: ExecutionStore) -> None:
        self.execution = execution
        self.store = execution.store

    def _incident(
        self,
        conn: psycopg.Connection[dict[str, object]],
        current: ExecutionState,
        batch: VenueFillBatch,
        reason: Reason,
    ) -> None:
        source = digest(canonical(batch))
        stable = digest(
            json.dumps(
                [
                    batch.execution_request_id,
                    batch.request_sha256,
                    batch.venue_order_id,
                    batch.raw_json,
                    batch.order_observation.status,
                    format(batch.order_observation.filled_quantity, "f"),
                    reason,
                ],
                separators=(",", ":"),
            )
        )
        previous = conn.execute(
            "SELECT 1 FROM ct_reconciliation_incidents WHERE incident_id=%s",
            ("incident:" + stable,),
        ).fetchone()
        if previous is not None:
            return  # same unresolved financial fault does not emit repeated critical alerts
        incident = ExecutionIncident(
            incident_id="incident:" + stable,
            tenant_id=current.request.tenant_id,
            actor_id=current.request.actor_id,
            execution_request_id=current.request.execution_request_id,
            source_digest=source,
            reason_code=reason,
            occurred_at=batch.observed_at,
        )
        body = canonical(incident)
        conn.execute(
            "INSERT INTO ct_reconciliation_incidents "
            "(incident_id,tenant_id,execution_request_id,source_digest,reason_code,body) "
            "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (
                incident.incident_id,
                incident.tenant_id,
                incident.execution_request_id,
                source,
                reason,
                body,
            ),
        )
        conn.execute(
            "INSERT INTO ct_execution_suspense(incident_id,execution_request_id,source_digest) "
            "VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
            (incident.incident_id, incident.execution_request_id, source),
        )
        fingerprint = digest(body)
        event = EventEnvelope(
            event_id="incident:" + fingerprint,
            event_type="ReconciliationCriticalMismatch.v1",
            schema_version="1",
            occurred_at=incident.occurred_at,
            tenant_id=incident.tenant_id,
            actor_id=incident.actor_id,
            source_service="reconciliation",
            trace_id=incident.incident_id,
            correlation_id=incident.execution_request_id,
            payload=PayloadReference(
                artifact_ref=fingerprint,
                sha256=fingerprint,
                payload_schema_ref="ExecutionIncident.v1",
            ),
        )
        self.store.append_in_transaction(conn, event, incident)

    def apply(self, observation: VenueOrderObservation, batch: VenueFillBatch) -> ExecutionState:
        observation = VenueOrderObservation.model_validate(observation.model_dump())
        batch = VenueFillBatch.model_validate(batch.model_dump())
        current = self.execution.load(batch.execution_request_id)
        request = current.request
        if request.execution_mode != "SIMULATION" or observation.action != "QUERY":
            raise StateUnavailable("fixture settlement has no signed/live authority")
        expected = (
            request.tenant_id,
            request.venue_account_ref,
            request.execution_request_id,
            digest(canonical(request)),
            request.client_order_id,
            request.symbol,
            request.side,
        )
        observed = (
            observation.tenant_id,
            observation.venue_account_ref,
            observation.execution_request_id,
            observation.request_sha256,
            observation.client_order_id,
            observation.symbol,
            observation.side,
        )
        sourced = (
            batch.tenant_id,
            batch.venue_account_ref,
            batch.execution_request_id,
            batch.request_sha256,
            batch.client_order_id,
            batch.symbol,
            batch.side,
        )
        if (
            expected != observed
            or expected != sourced
            or observation.venue_order_id != batch.venue_order_id
        ):
            raise StateUnavailable("fill settlement ownership/source mismatch")
        if batch.order_observation != observation:
            raise StateUnavailable("order query and fill source proof mismatch")
        if observation.requested_quantity != request.quantity:
            raise StateUnavailable("fill settlement order quantity mismatch")
        body = canonical(batch)
        with self.store.connection() as conn:
            self.execution._lock(conn, request.tenant_id)
            current = self.execution._load(conn, request.execution_request_id)
            conn.execute(
                "INSERT INTO ct_execution_fill_sources "
                "(digest,execution_request_id,body,observed_at) "
                "VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (digest(body), request.execution_request_id, body, batch.observed_at),
            )
            if not batch.available or not batch.complete:
                self._incident(conn, current, batch, "UNPROVEN_FILL_BATCH")
                return current
            with localcontext() as exact:
                exact.prec = 100
                total = sum((entry.fill.quantity for entry in batch.fills), Decimal(0))
            if total != observation.filled_quantity or total < current.filled_quantity:
                self._incident(conn, current, batch, "CUMULATIVE_MISMATCH")
                return current
            if current.state in {
                OrderState.FILLED,
                OrderState.CANCELLED,
                OrderState.REJECTED,
                OrderState.EXPIRED,
            }:
                if total != current.filled_quantity:
                    self._incident(conn, current, batch, "TERMINAL_STATE_CONFLICT")
                else:
                    for entry in batch.fills:
                        prior = conn.execute(
                            "SELECT digest FROM ct_execution_fills WHERE tenant_id=%s "
                            "AND venue_account_ref=%s AND symbol=%s AND raw_trade_id=%s",
                            (
                                entry.tenant_id,
                                entry.venue_account_ref,
                                entry.symbol,
                                entry.raw_trade_id,
                            ),
                        ).fetchone()
                        if prior is None or prior["digest"] != digest(canonical(entry)):
                            self._incident(conn, current, batch, "FILL_ID_CONFLICT")
                            break
                return current
            if current.state not in {
                OrderState.RECOVERY_REQUIRED,
                OrderState.ACKNOWLEDGED,
                OrderState.PARTIALLY_FILLED,
                OrderState.CANCEL_PENDING,
            }:
                raise StateUnavailable("fill settlement requires an owned submitted order")
            row = conn.execute(
                "SELECT body FROM ct_risk_evaluations WHERE record_digest=%s",
                (request.risk_record_sha256,),
            ).fetchone()
            if row is None:
                raise StateUnavailable("fill attribution metadata unavailable")
            record = RiskEvaluationRecord.model_validate_json(str(row["body"]))
            metadata = record.context.metadata
            reason: Reason = "ACCOUNTING_ATTRIBUTION_FAILED"
            before_settlement = current
            try:
                with (
                    conn.transaction()
                ):  # savepoint: preserve source and incident on attribution failure
                    for entry in batch.fills:
                        fill = entry.fill
                        if (
                            fill.order_id != request.order_id
                            or not request.created_at - timedelta(seconds=1)
                            <= fill.timestamp
                            <= batch.observed_at
                        ):
                            raise ValueError("fill order/clock attribution mismatch")
                        fingerprint = digest(canonical(entry))
                        prior = conn.execute(
                            "SELECT digest FROM ct_execution_fills WHERE tenant_id=%s "
                            "AND venue_account_ref=%s AND symbol=%s AND raw_trade_id=%s",
                            (
                                entry.tenant_id,
                                entry.venue_account_ref,
                                entry.symbol,
                                entry.raw_trade_id,
                            ),
                        ).fetchone()
                        if prior is not None:
                            if prior["digest"] != fingerprint:
                                reason = "FILL_ID_CONFLICT"
                                raise ConflictError("venue fill ID changed body")
                            continue
                        tx = account_fill(
                            "fill-tx:" + fingerprint,
                            request.tenant_id,
                            "fill-source:" + fingerprint,
                            request.actor_id,
                            "venue-fill:" + fingerprint,
                            fill.timestamp,
                            request.portfolio_id,
                            request.side,
                            metadata.base_asset,
                            metadata.quote_asset,
                            fill,
                            "venue-fill:" + fingerprint,
                        )
                        LedgerStore(self.store).append_in_transaction(conn, tx)
                        conn.execute(
                            "INSERT INTO ct_execution_fills "
                            "(tenant_id,venue_account_ref,symbol,raw_trade_id,"
                            "execution_request_id,digest,body,ledger_tx_id) "
                            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                entry.tenant_id,
                                entry.venue_account_ref,
                                entry.symbol,
                                entry.raw_trade_id,
                                entry.execution_request_id,
                                fingerprint,
                                canonical(entry),
                                tx.transaction_id,
                            ),
                        )
                    if observation.status == "FILLED" and total == request.quantity:
                        target = OrderState.FILLED
                    elif observation.status in {"CANCELED", "EXPIRED"}:
                        target = (
                            OrderState.CANCELLED
                            if observation.status == "CANCELED"
                            else OrderState.EXPIRED
                        )
                        proof = conn.execute(
                            "SELECT * FROM ct_execution_reservations WHERE execution_request_id=%s",
                            (request.execution_request_id,),
                        ).fetchone()
                        if proof is None:
                            raise StateUnavailable(
                                "terminal cancellation reservation proof unavailable"
                            )
                        remaining_row = conn.execute(
                            "SELECT COALESCE(sum(p.amount),0) balance FROM ct_ledger_postings p "
                            "JOIN ct_ledger_transactions t USING(transaction_id) "
                            "WHERE p.tenant_id=%s "
                            "AND p.portfolio_id=%s AND p.account='RESERVED' "
                            "AND p.asset=%s AND t.related_order_id=%s",
                            (
                                request.tenant_id,
                                request.portfolio_id,
                                proof["reserve_asset"],
                                request.order_id,
                            ),
                        ).fetchone()
                        if remaining_row is None or not isinstance(
                            remaining_row["balance"], Decimal
                        ):
                            raise StateUnavailable("exact remaining reservation unavailable")
                        remaining = remaining_row["balance"]
                        if remaining > 0:
                            account_value = proof["reserve_account"]
                            account: Account
                            if account_value == "AVAILABLE":
                                account = "AVAILABLE"
                            elif account_value == "INVENTORY":
                                account = "INVENTORY"
                            else:
                                raise ValueError("invalid reservation custody proof")
                            if account not in {"AVAILABLE", "INVENTORY"}:
                                raise ValueError("invalid reservation custody proof")
                            release = move(
                                "terminal-release:" + request.execution_request_id,
                                request.tenant_id,
                                "terminal-release-source:" + request.execution_request_id,
                                request.actor_id,
                                "venue-fill-batch:" + digest(body),
                                batch.observed_at,
                                request.portfolio_id,
                                str(proof["reserve_asset"]),
                                remaining,
                                "RELEASE",
                                request.order_id,
                                reserve_account=account,
                            )
                            LedgerStore(self.store).append_in_transaction(conn, release)
                    elif observation.status == "PARTIALLY_FILLED" and 0 < total < request.quantity:
                        target = OrderState.PARTIALLY_FILLED
                    elif observation.status == "NEW" and total == 0:
                        target = OrderState.ACKNOWLEDGED
                    else:
                        raise ValueError("terminal/cumulative venue status incoherent")
                    if target == current.state and total == current.filled_quantity:
                        return current
                    if target not in ALLOWED.get(current.state, frozenset()):
                        unknown = transition(
                            current,
                            OrderState.UNKNOWN,
                            batch.observed_at,
                            "VENUE_TERMINAL_STATE_REQUIRES_RECOVERY",
                            "reconciliation:" + digest(body),
                        )
                        self.execution._write(conn, unknown)
                        recovery = transition(
                            unknown.resulting_state,
                            OrderState.RECOVERY_REQUIRED,
                            batch.observed_at,
                            "CANONICAL_VENUE_TERMINAL_PROOF",
                            "reconciliation:" + digest(body),
                        )
                        self.execution._write(conn, recovery)
                        current = recovery.resulting_state
                    change = transition(
                        current,
                        target,
                        batch.observed_at,
                        "CANONICAL_FILLS_SETTLED",
                        "reconciliation:" + digest(body),
                        filled=total,
                        venue_id=batch.venue_order_id,
                    )
                    self.execution._write(conn, change)
                    return change.resulting_state
            except (InsufficientFunds, ConflictError, ValueError, psycopg.IntegrityError):
                self._incident(conn, before_settlement, batch, reason)
                return before_settlement
