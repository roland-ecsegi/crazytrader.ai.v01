"""Official SDK wire/fault fixture ONLY. Fixed dummy auth and literal loopback endpoint.

Runs in the already locked isolated Spot SDK environment. It cannot reach Binance,
accept owner credentials or enable live/testnet transport. Not a production simulator.
"""

import json
import sys
from urllib.parse import urlsplit

from binance_common.configuration import ConfigurationRestAPI
from binance_sdk_spot.spot import Spot


def main() -> None:
    raw = json.load(sys.stdin)
    endpoint = raw["endpoint"]
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("fixture transport requires literal loopback HTTP")
    request = raw["request"]
    if request["execution_mode"] != "SIMULATION" or request["side"] != "SELL":
        raise ValueError("fixture transport has no real-money authority")
    config = ConfigurationRestAPI(
        api_key="fixture-only-key",
        api_secret="fixture",
        base_path=endpoint,
        timeout=150,
        retries=0,
        backoff=0,
    )
    client = Spot(config_rest_api=config)
    # Public fixture endpoint cannot redirect the mature SDK outside loopback.
    client.rest_api._session.max_redirects = 0
    try:
        if raw["action"] == "SUBMIT":
            # SDK generated annotation is float, but its serializer accepts the exact
            # decimal string unchanged. Actual wire test is mandatory; never cast float.
            response = client.rest_api.new_order(
                symbol=request["symbol"],
                side=request["side"],
                type=request["order_type"],
                quantity=request["quantity"],
                new_client_order_id=request["client_order_id"],
                new_order_resp_type="RESULT",
            )
        elif raw["action"] == "QUERY":
            response = client.rest_api.get_order(
                symbol=request["symbol"], orig_client_order_id=request["client_order_id"]
            )
        else:
            raise ValueError("fixture endpoint action unavailable")
        print(json.dumps({"status": "OBSERVED", "order": response.data().to_dict()}))
    except Exception:
        # Ambiguous exception never becomes REJECTED; no error/URL/auth text emitted.
        print(json.dumps({"status": "UNKNOWN", "order": None}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "UNKNOWN", "order": None}))
        raise SystemExit(1) from None
