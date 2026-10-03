"""Single claimed send through fixed dummy-auth SDK fixture, no real venue transport."""

from collections.abc import Callable
from datetime import datetime

from crazytrader_contracts.execution import ExecutionState
from crazytrader_contracts.models import OrderState

from .fixture_transport import SDKFixtureTransport
from .store import ExecutionStore


class FixtureExecutionRunner:
    def __init__(
        self, store: ExecutionStore, transport: SDKFixtureTransport, clock: Callable[[], datetime]
    ) -> None:
        self.store, self.transport, self.clock = store, transport, clock

    def submit_once(self, request_id: str) -> ExecutionState:
        current = self.store.load(request_id)
        if current.state != OrderState.AUTHORIZED:
            return current
        bound = self.transport.dispatch_bound(current.request)
        self.store.bind_fixture_dispatch(bound)
        claim = self.store.claim_submission(request_id, self.clock(), dispatch_bound=bound)
        if claim is None:
            return self.store.load(request_id)
        observation = self.transport.submit(claim.request, self.clock())
        return self.store.record_submission(observation)
