"""HTTP response parsing cannot convert ambiguity into negative order proof."""

import json

import pytest
from crazytrader_contracts.absence import FixtureOrderLookup

from .test_states import NOW, request


@pytest.mark.parametrize(
    "status,body,negative",
    [
        (400, {"code": -2013, "msg": "Order does not exist."}, True),
        (500, {"code": -2013, "msg": "Order does not exist."}, False),
        (400, {"code": -2013, "msg": "Order does not exist.", "orderId": 1}, False),
        (400, {"code": "-2013", "msg": "Order does not exist."}, False),
        (400, {"code": -2013, "msg": None}, False),
    ],
)
def test_only_exact_captured_negative_error_is_lookup_evidence(status, body, negative):
    lookup = FixtureOrderLookup(
        request=request(),
        started_at=NOW,
        finished_at=NOW,
        available=True,
        http_status=status,
        raw_json=json.dumps(body),
    )
    assert lookup.explicitly_not_found is negative


def test_unavailable_partial_lookup_raw_is_never_negative_evidence():
    lookup = FixtureOrderLookup(
        request=request(),
        started_at=NOW,
        finished_at=NOW,
        available=False,
        http_status=None,
        raw_json="partial unparseable source",
    )
    assert not lookup.explicitly_not_found
