"""Isolated native simulation worker. No venue transport or credentials configured."""

import json
import os
import sys
from datetime import UTC, datetime
from decimal import localcontext
from importlib.metadata import version
from pathlib import Path

from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.simulation import NativeSimulationJob, NativeSimulationReceipt
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig, StrategyConfig
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
from nautilus_trader.model.identifiers import ClientOrderId, InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Currency, Money, Price, Quantity
from nautilus_trader.trading.strategy import Strategy


def simulate(job):
    if version("nautilus-trader") != job.engine_version:
        raise ValueError("pinned engine version unavailable")
    record = job.venue_rules.rules.symbol_record()
    filters = {row["filterType"]: row for row in record["filters"]}
    price_increment = Price.from_str(filters["PRICE_FILTER"]["tickSize"])
    size_increment = Quantity.from_str(filters["LOT_SIZE"]["stepSize"])
    if price_increment.as_decimal() <= 0 or size_increment.as_decimal() <= 0:
        raise ValueError("native supported positive increments required")
    base, quote = Currency.from_str(record["baseAsset"]), Currency.from_str(record["quoteAsset"])
    quantity = Quantity(job.quantity, size_increment.precision)
    bid = Price(job.reference_price, price_increment.precision)
    if quantity.as_decimal() != job.quantity or bid.as_decimal() != job.reference_price:
        raise ValueError("native financial representation would round approved values")
    with localcontext() as exact:
        exact.prec = 100
        ask = Price(job.reference_price + price_increment.as_decimal(), price_increment.precision)
        fee = job.costs.taker_fee_bps / 10000
    initial = [Money(job.starting_base, base), Money(job.starting_quote, quote)]
    if (
        initial[0].as_decimal() != job.starting_base
        or initial[1].as_decimal() != job.starting_quote
    ):
        raise ValueError("native starting money would round owned funds")
    delta = job.event_at - datetime(1970, 1, 1, tzinfo=UTC)
    nanos = (delta.days * 86400 + delta.seconds) * 1000000000 + delta.microseconds * 1000
    instrument = CurrencyPair(
        InstrumentId(Symbol(job.symbol), Venue("BINANCE")),
        Symbol(job.symbol),
        base,
        quote,
        price_increment.precision,
        size_increment.precision,
        price_increment,
        size_increment,
        nanos,
        nanos,
        maker_fee=fee,
        taker_fee=fee,
    )

    class NativeExecution(Strategy):
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
            self.submit_order(
                self.order_factory.market(
                    instrument.id,
                    OrderSide.SELL,
                    quantity,
                    client_order_id=ClientOrderId(job.client_order_id),
                )
            )

        def on_order_filled(self, event):
            self.fills.append(type(event).to_dict(event))

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True)))
    try:
        engine.add_venue(Venue("BINANCE"), OmsType.NETTING, AccountType.CASH, initial)
        engine.add_instrument(instrument)
        strategy = NativeExecution()
        engine.add_strategy(strategy)
        # Modeled quotes are explicitly declared in the job, not alleged venue depth.
        engine.add_data(
            [
                QuoteTick(instrument.id, bid, ask, quantity, quantity, nanos + i, nanos + i)
                for i in range(3)
            ]
        )
        engine.run()
        after = {
            currency.code: format(amount.as_decimal(), "f")
            for currency, amount in engine.cache.account_for_venue(Venue("BINANCE"))
            .balances_total()
            .items()
        }
        return dict(
            engine_version=job.engine_version,
            job_sha256=digest(canonical(job)),
            orders=len(engine.cache.orders()),
            fills=strategy.fills,
            before={
                base.code: format(job.starting_base, "f"),
                quote.code: format(job.starting_quote, "f"),
            },
            after=after,
        )
    finally:
        engine.dispose()


def main():
    data = json.load(sys.stdin)
    job = NativeSimulationJob.model_validate(data["job"])
    result_root = Path(data["result_root"])
    result_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = result_root / (digest(canonical(job)) + ".json")
    if target.exists():
        receipt = NativeSimulationReceipt.model_validate_json(target.read_text())
        if receipt.job != job:
            raise ValueError("immutable native result job collision")
    else:
        raw = None
        try:
            raw = json.dumps(simulate(job), sort_keys=True, separators=(",", ":"))
            receipt = NativeSimulationReceipt(
                job=job,
                job_sha256=digest(canonical(job)),
                observed_at=datetime.now(UTC),
                available=True,
                raw_json=raw,
            )
        except Exception:
            receipt = NativeSimulationReceipt(
                job=job,
                job_sha256=digest(canonical(job)),
                observed_at=datetime.now(UTC),
                available=False,
                raw_json=raw,
            )
        temporary = target.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(canonical(receipt))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
        directory = os.open(result_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    if data.get("interrupt_after_result") is True:
        os._exit(2)  # explicit simulation-only persistence fault, not an order retry
    print(canonical(receipt))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "UNKNOWN"}))
        raise SystemExit(1) from None
