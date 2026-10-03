"""Expiry proof requires exact whole-reservation original custody restoration."""

from decimal import Decimal

import pytest
from crazytrader_contracts.expiry import UnsentExecutionExpiry
from crazytrader_ledger.commands import release_custody, reserve_custody

from .test_states import request


def evidence():
    req = request()
    original = reserve_custody(
        "reserve",
        req.tenant_id,
        "source",
        req.actor_id,
        "proof",
        req.created_at,
        req.portfolio_id,
        "BTC",
        req.quantity,
        req.order_id,
        Decimal("0.6"),
        Decimal("0.4"),
    )
    release = release_custody(
        original,
        req.quantity,
        "release",
        "release-source",
        req.actor_id,
        "unsent-expiry:" + req.execution_request_id,
        req.expires_at,
    )
    return UnsentExecutionExpiry(
        request=req,
        original_reservation=original,
        release=release,
        actor_id=req.actor_id,
        occurred_at=req.expires_at,
    )


def test_expiry_whole_original_custody_proof_and_partial_release_denial():
    valid = evidence()
    with pytest.raises(ValueError, match="complete original custody"):
        UnsentExecutionExpiry.model_validate(
            valid.model_dump()
            | {
                "release": release_custody(
                    valid.original_reservation,
                    Decimal("0.5"),
                    "release",
                    "release-source",
                    valid.actor_id,
                    "proof",
                    valid.occurred_at,
                ).model_dump(),
            }
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor_id", "other"),
        ("tenant_id", "other"),
        ("portfolio_id", "other"),
        ("execution_mode", "LIVE"),
    ],
)
def test_expiry_rejects_borrowed_or_live_request(field, value):
    valid = evidence()
    changed = valid.model_dump()
    changed["request"][field] = value
    with pytest.raises(ValueError):
        UnsentExecutionExpiry.model_validate(changed)
