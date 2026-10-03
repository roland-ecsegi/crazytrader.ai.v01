"""Deterministically export/check versioned schema artifacts."""

import argparse
import json
from pathlib import Path

from crazytrader_contracts import execution, ledger, market, models, risk
from crazytrader_contracts.events import EventEnvelope
from crazytrader_platform.storage import HealthChange

ROOT = Path(__file__).resolve().parents[1]
TYPES = [
    execution.ExecutionRequest,
    execution.ExecutionState,
    execution.ExecutionTransition,
    risk.RiskBoundaryRejection,
    risk.RiskEvaluationDecision,
    risk.CancellationRequest,
    risk.CancellationContext,
    risk.CancellationAuthorization,
    risk.PolicyAuthorization,
    risk.OwnerRiskConfiguration,
    risk.VenueSafetyFact,
    risk.RiskEvaluationRecord,
    risk.PortfolioSafetyFact,
    risk.MarketSafetyFact,
    risk.OperatingControls,
    risk.RiskLimits,
    risk.RiskContext,
    risk.RiskAuthorization,
    ledger.LedgerPosting,
    ledger.AssetBalance,
    ledger.PositionAttribution,
    ledger.PortfolioSnapshot,
    ledger.LedgerTransaction,
    models.TradeIntent,
    models.RiskDecision,
    models.PolicyDecision,
    models.Order,
    models.Fill,
    models.Portfolio,
    models.StrategyVersion,
    models.ModelVersion,
    models.AuditEvent,
    models.CertificationState,
    EventEnvelope,
    HealthChange,
    market.MarketTrade,
    market.MarketStatus,
    market.MarketCandle,
    market.BookSnapshot,
    market.BookDelta,
    market.InstrumentMetadata,
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    check = parser.parse_args().check
    destination = ROOT / "packages/contracts/schemas/v1"
    destination.mkdir(parents=True, exist_ok=True)
    for model in TYPES:
        for mode in ("validation", "serialization"):
            content = (
                json.dumps(model.model_json_schema(mode=mode), indent=2, sort_keys=True) + "\n"
            )
            path = destination / f"{model.__name__}.{mode}.json"
            if check:
                if not path.exists() or path.read_text() != content:
                    raise SystemExit(f"schema drift: {path.relative_to(ROOT)}")
            else:
                path.write_text(content)
    print("V1 schemas match" if check else "V1 schemas exported")


if __name__ == "__main__":
    main()
