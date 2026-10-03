"""Fixed loopback official-SDK fault transport, credentials are dummy constants.

No Binance URLs, no owner-local auth, no API/agent endpoint. Phase5 wire proof only.
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.execution import ExecutionRequest, VenueOrderObservation


class SDKFixtureTransport:
    def __init__(self, endpoint: str, sdk_python: Path, child: Path) -> None:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.port is None
            or parsed.path not in {"", "/"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("SDK fixture endpoint must be literal loopback")
        self.endpoint, self.sdk_python, self.child = endpoint, sdk_python, child

    def _call(
        self, request: ExecutionRequest, action: Literal["SUBMIT", "QUERY"], now: datetime
    ) -> VenueOrderObservation:
        request = ExecutionRequest.model_validate(request.model_dump())
        if request.execution_mode != "SIMULATION" or request.side != "SELL":
            raise ValueError("fixture SDK transport has no real-money authority")
        base = {
            "action": action,
            "tenant_id": request.tenant_id,
            "venue_account_ref": request.venue_account_ref,
            "execution_request_id": request.execution_request_id,
            "request_sha256": digest(canonical(request)),
            "client_order_id": request.client_order_id,
            "venue_order_id": None,
            "symbol": request.symbol,
            "side": request.side,
            "requested_quantity": request.quantity,
            "filled_quantity": "0",
            "status": "UNKNOWN",
            "observed_at": now,
        }
        try:
            # No inherited credentials, API keys, owner auth or arbitrary SDK configuration.
            env = {key: value for key, value in os.environ.items() if key in {"PATH", "SYSTEMROOT"}}
            env.update(NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
            result = subprocess.run(
                [str(self.sdk_python), str(self.child)],
                input=json.dumps(
                    {
                        "endpoint": self.endpoint,
                        "action": action,
                        "request": request.model_dump(mode="json"),
                    }
                ),
                env=env,
                timeout=5,
                capture_output=True,
                text=True,
            )
            raw = json.loads(result.stdout)
            if (
                result.returncode
                or raw["status"] != "OBSERVED"
                or not isinstance(raw["order"], dict)
            ):
                raise ValueError("ambiguous SDK response")
            order = raw["order"]
            if (order["clientOrderId"], order["symbol"], order["side"], order["origQty"]) != (
                request.client_order_id,
                request.symbol,
                request.side,
                format(request.quantity, "f"),
            ):
                raise ValueError("venue observation identity/quantity mismatch")
            if isinstance(order["orderId"], bool) or not isinstance(order["orderId"], int):
                raise ValueError("venue ID must be exact integer")
            observation = VenueOrderObservation.model_validate(
                base
                | {
                    "venue_order_id": str(order["orderId"]),
                    "filled_quantity": order["executedQty"],
                    "status": order["status"],
                }
            )
            return observation
        except Exception:
            return VenueOrderObservation.model_validate(base)

    def submit(self, request: ExecutionRequest, now: datetime) -> VenueOrderObservation:
        return self._call(request, "SUBMIT", now)

    def query(self, request: ExecutionRequest, now: datetime) -> VenueOrderObservation:
        return self._call(request, "QUERY", now)
