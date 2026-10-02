"""Offline candidate compatibility evidence. Never connects to an exchange."""

import hashlib
import inspect
import json
from decimal import Decimal
from importlib.metadata import distribution
from pathlib import Path

from binance_common.configuration import ConfigurationRestAPI
from binance_sdk_spot.spot import Spot
from nautilus_trader.adapters.binance import BinanceExecClientConfig
from nautilus_trader.adapters.binance.common.enums import BinanceAccountType
from nautilus_trader.adapters.binance.execution import BinanceCommonExecutionClient
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.test_kit.providers import TestInstrumentProvider


def main() -> None:
    packages = {}
    for name in ("nautilus-trader", "binance-sdk-spot", "binance-common"):
        dist = distribution(name)
        licenses = []
        for file in dist.files or []:
            if "license" in str(file).lower() or "licence" in str(file).lower():
                content = dist.locate_file(file).read_bytes()
                licenses.append({"file": str(file), "sha256": hashlib.sha256(content).hexdigest()})
        packages[name] = {
            "version": dist.version,
            "license": dist.metadata.get("License"),
            "python": dist.metadata.get("Requires-Python"),
            "license_files": licenses,
        }
    instrument = TestInstrumentProvider.btcusdt_binance()
    assert instrument.id.value == "BTCUSDT.BINANCE"
    assert Price.from_str("123.4500").as_decimal() == Decimal("123.4500")
    assert Quantity.from_str("0.0100").as_decimal() == Decimal("0.0100")
    client_id = ClientOrderId("ct-ti-001")
    assert ClientOrderId(client_id.value) == client_id
    config = BinanceExecClientConfig(
        account_type=BinanceAccountType.SPOT, testnet=True, max_retries=0
    )
    assert config.testnet and config.max_retries == 0
    sdk_config = ConfigurationRestAPI(base_path="http://127.0.0.1:1", retries=0)
    spot = Spot(config_rest_api=sdk_config)
    assert spot.rest_api is not None  # object construction only, no HTTP call
    assert sdk_config.retries == 0
    assert callable(spot.rest_api.get_order)
    assert callable(spot.rest_api.exchange_info)
    source = inspect.getsource(BinanceCommonExecutionClient._submit_order_inner)
    assert "generate_order_rejected" in source
    # This source probe records a hazard; it is not a timeout/recovery test.
    evidence = {
        "packages": packages,
        "offline_checks": [
            "decimal precision",
            "stable ID",
            "Spot instrument fixture",
            "testnet config",
            "SDK construction/no retries",
            "query/filter API presence",
        ],
        "execution_hazard": (
            "submission failure can emit REJECTED; UNKNOWN/reconciliation wrapper "
            "and injected timeout proof required before live adoption"
        ),
        "venue_calls": 0,
        "certification": "L0",
    }
    path = Path(__file__).resolve().parents[3] / "docs/evidence/spikes/python-compatibility.json"
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print("offline compatibility PASS; live execution adoption deferred")


if __name__ == "__main__":
    main()
