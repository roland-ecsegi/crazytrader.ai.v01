"""Single claimed send through fixed dummy-auth SDK fixture, no real venue transport."""

from collections.abc import Callable
from datetime import datetime

from crazytrader_contracts.execution import ExecutionState

from .fixture_transport import SDKFixtureTransport
from .store import ExecutionStore


class FixtureExecutionRunner:
    def __init__(
        self, store: ExecutionStore, transport: SDKFixtureTransport, clock: Callable[[], datetime]
    ) -> None:
        self.store, self.transport, self.clock = store, transport, clock

    def submit_once(self, request_id: str) -> ExecutionState:
        claim = self.store.claim_submission(request_id, self.clock())
        if claim is None:
            return self.store.load(request_id)
        observation = self.transport.submit(claim.request, self.clock())
        return self.store.record_submission(observation)
