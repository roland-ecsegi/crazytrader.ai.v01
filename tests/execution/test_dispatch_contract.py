"""Immutable reviewed signed guard source and captured server date clock proofs."""

from datetime import timedelta
from email.utils import format_datetime
from pathlib import Path

import pytest
from crazytrader_contracts.absence import FixtureOrderLookup, FixtureTimedOrderLookup
from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.dispatch import FixtureDispatchBound

from .test_states import NOW, request


def bound():
    req = request()
    child = Path("services/execution/sdk_fixture_transport.py")
    return FixtureDispatchBound.model_validate(
        dict(
            request=req,
            request_sha256=digest(canonical(req)),
            bound_at=NOW,
            child_source_sha256=digest(child.read_text()),
        )
    )


def test_only_reviewed_guard_source_and_original_live_deadline_can_bind_dispatch():
    valid = bound()
    with pytest.raises(ValueError):
        FixtureDispatchBound.model_validate(valid.model_dump() | {"child_source_sha256": "a" * 64})
    with pytest.raises(ValueError, match="original scoped"):
        FixtureDispatchBound.model_validate(
            valid.model_dump() | {"bound_at": valid.request.expires_at}
        )
    with pytest.raises(ValueError, match="original scoped"):
        FixtureDispatchBound.model_validate(valid.model_dump() | {"request_sha256": "a" * 64})


def test_timed_lookup_cannot_supply_an_unbound_or_altered_server_clock():
    lookup = FixtureOrderLookup(
        request=request(),
        started_at=NOW,
        finished_at=NOW,
        available=False,
        http_status=None,
        raw_json=None,
    )
    date = format_datetime(NOW, usegmt=True)
    with pytest.raises(ValueError, match="paired"):
        FixtureTimedOrderLookup(lookup=lookup, server_date=NOW, raw_server_date=None)
    with pytest.raises(ValueError, match="captured HTTP date"):
        FixtureTimedOrderLookup(
            lookup=lookup, server_date=NOW + timedelta(seconds=1), raw_server_date=date
        )
    assert (
        FixtureTimedOrderLookup(lookup=lookup, server_date=NOW, raw_server_date=date).server_date
        == NOW
    )
