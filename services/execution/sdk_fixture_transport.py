"""Official SDK wire/fault fixture ONLY. Fixed dummy auth and literal loopback endpoint.

Runs in the already locked isolated Spot SDK environment. It cannot reach Binance,
accept owner credentials or enable live/testnet transport. Not a production simulator.
"""

import json
import sys
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlsplit

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
        timeout=150 if raw["action"] in {"SUBMIT", "CANCEL"} else 1000,
        retries=0,
        backoff=0,
    )
    client = Spot(config_rest_api=config)
    # Public fixture endpoint cannot redirect the mature SDK outside loopback.
    client.rest_api._session.max_redirects = 0
    client.rest_api._session.trust_env = False  # no proxy/netrc credential fallback
    if raw["action"] == "SUBMIT":
        deadline = datetime.fromisoformat(request["expires_at"].replace("Z", "+00:00"))
        delta = deadline - datetime(1970, 1, 1, tzinfo=UTC)
        deadline_ms = (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000

        def guard_submission(prepared):
            target = urlsplit(prepared.url)
            body = prepared.body or ""
            if isinstance(body, bytes):
                body = body.decode("ascii")
            fields = parse_qs(target.query)
            for name, values in parse_qs(body).items():
                if name in fields:
                    raise ValueError("duplicate signed dispatch field")
                fields[name] = values
            timestamp = fields.get("timestamp", [])
            if (
                datetime.now(UTC) >= deadline
                or prepared.method != "POST"
                or target.hostname != "127.0.0.1"
                or target.port != parsed.port
                or target.path != "/api/v3/order"
                or len(timestamp) != 1
                or not timestamp[0].isdigit()
                or int(timestamp[0]) > deadline_ms
                or fields.get("recvWindow") != ["5000"]
                or fields.get("newClientOrderId") != [request["client_order_id"]]
            ):
                raise ValueError("expired or unbounded original signed dispatch")
            return prepared  # validate the official SDK request without changing its signature

        client.rest_api._session.auth = guard_submission
    try:
        if raw["action"] == "LOOKUP":
            captured = {}

            def capture(response, *args, **kwargs):
                target = urlsplit(response.request.url)
                params = parse_qs(target.query)
                if (
                    response.request.method != "GET"
                    or target.hostname != "127.0.0.1"
                    or target.port != parsed.port
                    or target.path != "/api/v3/order"
                    or params.get("origClientOrderId") != [request["client_order_id"]]
                    or params.get("symbol") != [request["symbol"]]
                    or len(response.content) > 64000
                ):
                    return
                data = response.json()
                if isinstance(data, dict):
                    captured.update(
                        http_status=response.status_code,
                        body=data,
                        server_date=None,
                        raw_date=response.headers.get("Date"),
                    )
                    if captured["raw_date"]:
                        parsed_date = parsedate_to_datetime(captured["raw_date"])
                        if (
                            parsed_date.utcoffset() is not None
                            and parsed_date.utcoffset().total_seconds() == 0
                        ):
                            captured["server_date"] = parsed_date.isoformat()

            client.rest_api._session.hooks["response"].append(capture)
            try:
                client.rest_api.get_order(
                    symbol=request["symbol"], orig_client_order_id=request["client_order_id"]
                )
            except Exception:
                pass  # capture retains HTTP source; exception is never negative proof
            print(json.dumps({"status": "OBSERVED" if captured else "UNKNOWN", "lookup": captured}))
            return
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
                recv_window=5000,
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
