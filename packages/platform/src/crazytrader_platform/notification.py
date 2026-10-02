"""Observable local alert delivery; never dispatches external messages in cloud."""

import logging
from collections.abc import Callable

from crazytrader_platform.storage import EventStore


class NotificationWorker:
    def __init__(self, store: EventStore, sink: Callable[[str], None] | None = None) -> None:
        self.store = store
        self.sink = sink or self.console_sink

    @staticmethod
    def console_sink(event_id: str) -> None:
        # Validated identifier only; payload/credentials never logged.
        logging.getLogger("crazytrader.alerts").warning(
            "critical platform alert event=%s", event_id
        )

    def deliver(self) -> int:
        delivered = 0
        for event_id in self.store.notifications():
            try:
                self.sink(event_id)
            except Exception:
                self.store.notification_attempt(event_id, False)
            else:
                self.store.notification_attempt(event_id, True)
                delivered += 1
        return delivered
