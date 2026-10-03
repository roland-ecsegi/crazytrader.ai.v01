"""Elapsed signed-window absence proof restoring original simulation custody."""

from datetime import timedelta
from typing import Literal, Self

from pydantic import model_validator

from .absence import FixtureAbsenceAssessment, FixtureTimedOrderLookup
from .dispatch import FixtureDispatchBound
from .expiry import UnsentExecutionExpiry
from .ledger import LedgerTransaction
from .models import Contract, Identifier, Timestamp


class FixtureAbsenceClosure(Contract):
    schema_version: Literal["1"] = "1"
    assessment: FixtureAbsenceAssessment
    dispatch_bound: FixtureDispatchBound
    timed_lookup: FixtureTimedOrderLookup
    original_reservation: LedgerTransaction
    release: LedgerTransaction
    actor_id: Identifier
    occurred_at: Timestamp
    certification_effect: Literal["NONE"] = "NONE"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        request = self.assessment.state.request
        timed = self.timed_lookup
        if (
            self.assessment.verdict != "PROVEN"
            or self.dispatch_bound.request != request
            or timed.lookup != self.assessment.lookup
            or self.actor_id != self.assessment.actor_id
            or timed.server_date is None
            or timed.server_date < request.expires_at + timedelta(seconds=6)
            or not timed.lookup.started_at - timedelta(seconds=1)
            <= timed.server_date
            <= timed.lookup.finished_at + timedelta(seconds=1)
            or not self.assessment.occurred_at <= self.occurred_at
            or self.occurred_at - timed.lookup.started_at > timedelta(seconds=10)
            or self.release.provenance_ref != "fixture-absent:" + request.execution_request_id
        ):
            raise ValueError("fresh original elapsed-window absence proof required")
        # Reuse exact inverse-custody validation, without asserting an unsent source.
        UnsentExecutionExpiry(
            request=request,
            original_reservation=self.original_reservation,
            release=self.release,
            actor_id=self.actor_id,
            occurred_at=self.occurred_at,
        )
        return self
