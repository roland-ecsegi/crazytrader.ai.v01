"""Isolated official SDK worker. Fixed public GET allowlist; no credentials."""

import json
import sys

from binance_common.configuration import ConfigurationRestAPI
from binance_sdk_spot.spot import Spot

ENDPOINTS = {
    "SANDBOX": "https://testnet.binance.vision",
    "PUBLIC": "https://data-api.binance.vision",  # market-data-only Binance host
}


def main() -> None:
    request = json.load(sys.stdin)
    if set(request) != {"environment", "operation", "symbol", "limit", "from_id"}:
        raise ValueError("invalid read request")
    environment = request["environment"]
    symbol = request["symbol"]
    if environment not in ENDPOINTS or not isinstance(symbol, str) or not symbol.isalnum():
        raise ValueError("invalid market source")
    limit = request["limit"]
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("invalid market request limit")
    config = ConfigurationRestAPI(base_path=ENDPOINTS[environment], timeout=5000, retries=0)
    client = Spot(config_rest_api=config).rest_api
    if request["operation"] == "exchange_info":
        response = client.exchange_info(symbol=symbol)
    elif request["operation"] == "agg_trades":
        from_id = request["from_id"]
        if from_id is not None and (type(from_id) is not int or from_id < 0):
            raise ValueError("invalid trade cursor")
        response = client.agg_trades(symbol=symbol, limit=limit, from_id=from_id)
    elif request["operation"] == "depth":
        response = client.depth(symbol=symbol, limit=min(limit, 100))
    else:
        raise ValueError("unsupported read-only operation")
    body = response.data()
    if isinstance(body, list):
        body = [item.to_dict() for item in body]
    else:
        body = body.to_dict()
    json.dump(body, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("read-only venue request failed") from None
