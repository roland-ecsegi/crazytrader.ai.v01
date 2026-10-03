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
        if raw["action"] == "ACCOUNT":
            symbols = raw["symbols"]
            if (
                not isinstance(symbols, list)
                or not 1 <= len(symbols) <= 32
                or len(set(symbols)) != len(symbols)
            ):
                raise ValueError("bounded unique fixture symbol scope required")

            def pages(symbol, fills, result):
                cursor = 0
                for _ in range(20):
                    response = (
                        client.rest_api.my_trades(symbol=symbol, from_id=cursor, limit=1000)
                        if fills
                        else client.rest_api.all_orders(symbol=symbol, order_id=cursor, limit=1000)
                    )
                    page = [entry.to_dict() for entry in response.data()]
                    result.append(page)
                    if len(page) < 1000:
                        return result
                    next_cursor = page[-1]["id" if fills else "orderId"] + 1
                    if next_cursor <= cursor:
                        raise ValueError("history pagination did not advance")
                    cursor = next_cursor
                raise ValueError("history page limit reached")

            data = {}
            try:
                data["before"] = client.rest_api.get_account().data().to_dict()
                data["open"] = [
                    entry.to_dict() for entry in client.rest_api.get_open_orders().data()
                ]
                data["history"] = {}
                for symbol in symbols:
                    data["history"][symbol] = {"orders": [], "fills": []}
                    pages(symbol, False, data["history"][symbol]["orders"])
                    pages(symbol, True, data["history"][symbol]["fills"])
                data["after"] = client.rest_api.get_account().data().to_dict()
                print(json.dumps({"status": "OBSERVED", "account": data}))
            except Exception:
                print(json.dumps({"status": "UNKNOWN", "account": data}))
            return
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
        elif raw["action"] == "CANCEL":
            response = client.rest_api.delete_order(
                symbol=request["symbol"], orig_client_order_id=request["client_order_id"]
            )
        elif raw["action"] == "FILLS":
            response = client.rest_api.my_trades(
                symbol=request["symbol"], order_id=int(raw["venue_order_id"]), limit=1000
            )
            data = response.data()
            if not isinstance(data, list):
                raise ValueError("fill response must be an array")
            print(json.dumps({"status": "OBSERVED", "fills": [entry.to_dict() for entry in data]}))
            return
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
