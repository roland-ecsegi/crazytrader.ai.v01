"""Elapsed-window custody proof rejects borrowed clocks, sources and partial releases."""

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from crazytrader_contracts.absence import (
    FixtureAbsenceAssessment,
    FixtureOrderLookup,
    FixtureTimedOrderLookup,
)
from crazytrader_contracts.absence_closure import FixtureAbsenceClosure
from crazytrader_contracts.account import VenueAccountRead
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.dispatch import FixtureDispatchBound
from crazytrader_contracts.execution import ExecutionState
from crazytrader_ledger.commands import release_custody

from .test_expiry_contract import evidence


def closure():
    expiry = evidence()
    request = expiry.request
    clock = request.expires_at.replace(microsecond=0) + timedelta(seconds=7)
    state = ExecutionState(
        request=request,
        revision=4,
        state="UNKNOWN",
        filled_quantity="0",
        venue_order_id=None,
        created_at=request.created_at,
        updated_at=request.created_at,
    )
    lookup = FixtureOrderLookup(
        request=request,
        started_at=clock,
        finished_at=clock,
        available=True,
        http_status=400,
        raw_json=json.dumps({"code": -2013, "msg": "Absent"}),
    )
    account = {
        "balances": [],
        "canTrade": True,
        "canWithdraw": False,
        "accountType": "SPOT",
        "permissions": ["SPOT"],
    }
    read = VenueAccountRead(
        tenant_id=request.tenant_id,
        venue_account_ref=request.venue_account_ref,
        anchor_request_id=request.execution_request_id,
        anchor_request_sha256=digest(canonical(request)),
        symbols=(request.symbol,),
        started_at=clock,
        finished_at=clock,
        available=True,
        raw_json=json.dumps(
            {
                "before": account,
                "after": account,
                "open": [],
                "history": {request.symbol: {"orders": [[]], "fills": [[]]}},
            }
        ),
    )
    from email.utils import format_datetime

    timed = FixtureTimedOrderLookup(
        lookup=lookup, raw_server_date=format_datetime(clock, usegmt=True), server_date=clock
    )
    return FixtureAbsenceClosure(
        assessment=FixtureAbsenceAssessment(
            state=state,
            lookup=lookup,
            account=read,
            internal_head_sha256="a" * 64,
            actor_id=request.actor_id,
            verdict="PROVEN",
            findings=(),
            occurred_at=clock,
        ),
        dispatch_bound=FixtureDispatchBound(
            request=request,
            bound_at=request.created_at,
            request_sha256=digest(canonical(request)),
            child_source_sha256="113680db83443dacad4b124b407a298f75a1579ebdc0cf5d188833c2f937530b",
        ),
        timed_lookup=timed,
        original_reservation=expiry.original_reservation,
        release=release_custody(
            expiry.original_reservation,
            request.quantity,
            "release",
            "release-source",
            request.actor_id,
            "fixture-absent:" + request.execution_request_id,
            clock,
        ),
        actor_id=request.actor_id,
        occurred_at=clock,
    )


def test_original_whole_custody_closure_and_partial_release_denial():
    valid = closure()
    partial = release_custody(
        valid.original_reservation,
        Decimal("0.5"),
        "release",
        "source",
        valid.actor_id,
        valid.release.provenance_ref,
        valid.occurred_at,
    )
    with pytest.raises(ValueError, match="complete original custody"):
        FixtureAbsenceClosure.model_validate(valid.model_dump() | {"release": partial.model_dump()})


@pytest.mark.parametrize("fault", ["early-clock", "missing-clock", "borrowed-request"])
def test_clock_and_original_dispatch_binding_cannot_be_borrowed(fault):
    valid = closure()
    body = valid.model_dump()
    if fault == "early-clock":
        from email.utils import format_datetime

        clock = valid.assessment.state.request.expires_at.replace(microsecond=0)
        body["timed_lookup"].update(
            server_date=clock, raw_server_date=format_datetime(clock, usegmt=True)
        )
    elif fault == "missing-clock":
        body["timed_lookup"].update(server_date=None, raw_server_date=None)
    else:
        body["dispatch_bound"]["request"]["execution_request_id"] = "borrowed"
    with pytest.raises(ValueError):
        FixtureAbsenceClosure.model_validate(body)
