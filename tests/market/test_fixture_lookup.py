"""Actual official SDK signed raw lookup observation; no absence/retry grant."""

import os

import pytest
from crazytrader_execution.runner import FixtureExecutionRunner

from tests.execution.fixture_server import sdk_venue

from .test_execution_boundary import prepared_request
from .test_sdk_timeout import transport

pytestmark = pytest.mark.skipif(not os.getenv("CT_TEST_S3"), reason="actual services required")


def test_signed_lookup_distinguishes_unavailable_from_explicit_negative_response(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    with sdk_venue(risk.store, intent.tenant_id) as endpoint:
        ambiguous = transport(endpoint).lookup(request)
        assert not ambiguous.available
        assert not ambiguous.explicitly_not_found
    with sdk_venue(risk.store, intent.tenant_id, authoritative_not_found=True) as endpoint:
        negative = transport(endpoint).lookup(request)
        assert negative.available
        assert negative.http_status == 400
        assert negative.explicitly_not_found
        assert negative.raw()["code"] == -2013
        assert negative.request == request


def test_signed_lookup_finds_the_original_owned_order(backbone):
    risk, objects, intent, context, config, policy, now = backbone
    execution, request = prepared_request(backbone)
    with sdk_venue(risk.store, intent.tenant_id, timeout_after_accept=False) as endpoint:
        execution.prepare(request, objects, now)
        assert FixtureExecutionRunner(execution, transport(endpoint), lambda: now).submit_once(
            request.execution_request_id
        )
        present = transport(endpoint).lookup(request)
        assert present.available
        assert present.http_status == 200
        assert not present.explicitly_not_found
        assert present.raw()["clientOrderId"] == request.client_order_id
