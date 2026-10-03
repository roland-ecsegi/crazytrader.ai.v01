"""Official SDK generated model roundtrip and fixed GET capability, no network."""

import inspect

from binance_common.configuration import ConfigurationRestAPI
from binance_sdk_spot.rest_api.models.agg_trades_response_inner import AggTradesResponseInner
from binance_sdk_spot.rest_api.models.exchange_info_response import ExchangeInfoResponse
from binance_sdk_spot.spot import Spot

raw = {
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "0.01",
                    "maxPrice": "1000000",
                    "tickSize": "0.01",
                }
            ],
        }
    ]
}
model = ExchangeInfoResponse.from_dict(raw)
assert model is not None
assert model.to_dict()["symbols"][0]["filters"][0]["filterType"] == "PRICE_FILTER"
trade = AggTradesResponseInner.from_dict(
    {"a": 1, "p": "100.01", "q": "0.100", "T": 1790985600000, "m": False}
)
assert trade is not None and trade.to_dict()["p"] == "100.01"
config = ConfigurationRestAPI(base_path="https://testnet.binance.vision", timeout=5000, retries=0)
assert config.api_key is None and config.api_secret is None
client = Spot(config_rest_api=config).rest_api
for method, parameters in {
    "exchange_info": {"symbol"},
    "agg_trades": {"symbol", "limit", "from_id"},
    "depth": {"symbol", "limit"},
}.items():
    assert parameters <= set(inspect.signature(getattr(client, method)).parameters)
print("official SDK nested serialization and unsigned GET signatures PASS (offline)")
