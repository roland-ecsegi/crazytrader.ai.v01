"""Offline modeled mature simulation baseline; never configures exchange transport."""

import json
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig, StrategyConfig
from nautilus_trader.model.currencies import BTC, USDT
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
from nautilus_trader.model.identifiers import ClientOrderId, Venue
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from nautilus_trader.trading.strategy import Strategy

instrument = TestInstrumentProvider.btcusdt_binance()


class ApprovedSimulation(Strategy):
    def __init__(self):
        super().__init__(StrategyConfig())
        self.sent = False
        self.fills = []

    def on_start(self):
        self.subscribe_quote_ticks(instrument.id)

    def on_quote_tick(self, tick):
        if self.sent:
            return
        self.sent = True
        order = self.order_factory.market(
            instrument.id,
            OrderSide.SELL,
            Quantity.from_str("0.100000"),
            client_order_id=ClientOrderId("ct_probe_sell"),
        )
        self.submit_order(order)

    def on_order_filled(self, event):
        self.fills.append(type(event).to_dict(event))


def run_once():
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True)))
    try:
        engine.add_venue(
            Venue("BINANCE"),
            OmsType.NETTING,
            AccountType.CASH,
            [Money("1", BTC), Money("100", USDT)],
        )
        engine.add_instrument(instrument)
        strategy = ApprovedSimulation()
        engine.add_strategy(strategy)
        engine.add_data(
            [
                QuoteTick(
                    instrument.id,
                    Price.from_str("100.00"),
                    Price.from_str("100.01"),
                    Quantity.from_str("1.000000"),
                    Quantity.from_str("1.000000"),
                    1790985600000000000 + i * 1000000000,
                    1790985600000000000 + i * 1000000000,
                )
                for i in range(3)
            ]
        )
        engine.run()
        balances = {
            currency.code: format(amount.as_decimal(), "f")
            for currency, amount in engine.cache.account_for_venue(Venue("BINANCE"))
            .balances_total()
            .items()
        }
        return {"fills": strategy.fills, "orders": len(engine.cache.orders()), "balances": balances}
    finally:
        engine.dispose()


def financial_facts(result):
    return {
        "fills": [
            {
                key: row[key]
                for key in (
                    "client_order_id",
                    "venue_order_id",
                    "trade_id",
                    "order_side",
                    "last_qty",
                    "last_px",
                    "currency",
                    "commission",
                    "ts_event",
                )
            }
            for row in result["fills"]
        ],
        "orders": result["orders"],
        "balances": result["balances"],
    }


def main():
    assert version("nautilus-trader") == "1.221.0"
    first, second = run_once(), run_once()
    assert financial_facts(first) == financial_facts(second)
    assert first["orders"] == 1 and len(first["fills"]) == 1
    fill = first["fills"][0]
    assert (fill["last_qty"], fill["last_px"], fill["commission"]) == (
        "0.100000",
        "100.00",
        "0.01000000 USDT",
    )
    assert {asset: Decimal(value) for asset, value in first["balances"].items()} == {
        "BTC": Decimal("0.9"),
        "USDT": Decimal("109.99"),
    }
    evidence = {
        "engine": "unmodified dynamically imported nautilus-trader1.221.0",
        "certification": "L0",
        "certification_effect": "NONE",
        "mode": "SIMULATION",
        "data_source": "fixed modeled quote fixture, not observed venue prices",
        "cost_source": "instrument fixture taker_fee0.001, not verified venue fees",
        "network_calls": 0,
        "repeat_financial_facts_identical": True,
        "first_run": first,
        "second_run": second,
        "scope": "mature engine baseline; durable execution/ledger adapter integration pending",
    }
    path = Path(__file__).resolve().parents[3] / "docs/evidence/spikes/nautilus-simulation.json"
    path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    print("unmodified Nautilus simulation baseline PASS; no execution authority or phase gate")


if __name__ == "__main__":
    main()
