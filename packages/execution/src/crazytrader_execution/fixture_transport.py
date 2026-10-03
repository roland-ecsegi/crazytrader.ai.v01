"""Fixed loopback official-SDK fault transport, credentials are dummy constants.

No Binance URLs, no owner-local auth, no API/agent endpoint. Phase5 wire proof only.
"""

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from decimal import localcontext
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.execution import (
    CancellationEvaluationRecord,
    CancellationReceipt,
    ExecutionRequest,
    VenueFillBatch,
    VenueFillEvidence,
    VenueOrderObservation,
    VenueQuoteFillBatch,
)
from crazytrader_contracts.models import Fill, decimal_input
from crazytrader_contracts.venue_fills import QuoteFillIdentity, VenueQuoteFill
from crazytrader_contracts.venue_rules import VenueRuleReceipt


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

    def fills(
        self, request: ExecutionRequest, observation: VenueOrderObservation, now: datetime
    ) -> VenueFillBatch:
        request = ExecutionRequest.model_validate(request.model_dump())
        if request.execution_mode != "SIMULATION" or request.side != "SELL":
            raise ValueError("fixture fills have no real-money authority")
        observation = VenueOrderObservation.model_validate(observation.model_dump())
        venue_id = observation.venue_order_id
        if venue_id is None:
            raise ValueError("canonical fills require an identified query order")
        base = {
            "order_observation": observation,
            "tenant_id": request.tenant_id,
            "venue_account_ref": request.venue_account_ref,
            "execution_request_id": request.execution_request_id,
            "request_sha256": digest(canonical(request)),
            "client_order_id": request.client_order_id,
            "venue_order_id": venue_id,
            "symbol": request.symbol,
            "side": request.side,
            "observed_at": now,
            "raw_json": None,
            "available": False,
            "complete": False,
            "fills": (),
        }
        try:
            env = {key: value for key, value in os.environ.items() if key in {"PATH", "SYSTEMROOT"}}
            env.update(NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
            result = subprocess.run(
                [str(self.sdk_python), str(self.child)],
                input=json.dumps(
                    {
                        "endpoint": self.endpoint,
                        "action": "FILLS",
                        "request": request.model_dump(mode="json"),
                        "venue_order_id": venue_id,
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
                or not isinstance(raw["fills"], list)
            ):
                raise ValueError("fill source unavailable")
            rows = raw["fills"]
            base["raw_json"] = json.dumps(rows, sort_keys=True, separators=(",", ":"))
            fills = []
            for row in rows:
                if any(type(row.get(name)) is not int for name in ("id", "orderId", "time")):
                    raise ValueError("integer venue IDs and UTC epoch milliseconds required")
                if type(row.get("isBuyer")) is not bool or row["isBuyer"] is not False:
                    raise ValueError("fill direction mismatch")
                if row["symbol"] != request.symbol or str(row["orderId"]) != venue_id:
                    raise ValueError("fill order identity mismatch")
                scope = digest(
                    json.dumps(
                        [request.tenant_id, request.venue_account_ref, request.symbol, row["id"]],
                        separators=(",", ":"),
                    )
                )
                with localcontext() as exact:
                    exact.prec = 100
                    quantity, price = decimal_input(row["qty"]), decimal_input(row["price"])
                    if decimal_input(row["quoteQty"]) != quantity * price:
                        raise ValueError("fill quote amount mismatch")
                fill = Fill(
                    fill_id="fill:" + scope,
                    order_id=request.order_id,
                    venue_fill_id="vfill:" + scope,
                    quantity=quantity,
                    price=price,
                    fee_amount=row["commission"],
                    fee_asset=row["commissionAsset"],
                    timestamp=datetime(1970, 1, 1, tzinfo=UTC)
                    + timedelta(milliseconds=row["time"]),
                )
                fills.append(
                    VenueFillEvidence(
                        tenant_id=request.tenant_id,
                        venue_account_ref=request.venue_account_ref,
                        execution_request_id=request.execution_request_id,
                        client_order_id=request.client_order_id,
                        venue_order_id=venue_id,
                        symbol=request.symbol,
                        side=request.side,
                        raw_trade_id=row["id"],
                        fill=fill,
                    )
                )
            return VenueFillBatch.model_validate(
                base | {"available": True, "complete": len(rows) < 1000, "fills": tuple(fills)}
            )
        except Exception:
            return VenueFillBatch.model_validate(base)

    def cancel(
        self, request: ExecutionRequest, record: CancellationEvaluationRecord, now: datetime
    ) -> CancellationReceipt:
        request = ExecutionRequest.model_validate(request.model_dump())
        record = CancellationEvaluationRecord.model_validate(record.model_dump())
        if request.execution_mode != "SIMULATION" or request.side != "SELL":
            raise ValueError("fixture cancellation has no signed/live authority")
        if record.authorization.decision != "ALLOW" or not (
            record.authorization.evaluated_at <= now < record.authorization.expires_at
        ):
            raise ValueError("cancellation authorization expired or denied")
        if (
            record.execution_request_id,
            record.request.client_order_id,
            record.context.venue_account_ref,
            record.request.tenant_id,
        ) != (
            request.execution_request_id,
            request.client_order_id,
            request.venue_account_ref,
            request.tenant_id,
        ):
            raise ValueError("cancellation transport ownership mismatch")
        raw_json, outcome = None, "UNKNOWN"
        try:
            env = {k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT"}}
            env.update(NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
            result = subprocess.run(
                [str(self.sdk_python), str(self.child)],
                input=json.dumps(
                    {
                        "endpoint": self.endpoint,
                        "action": "CANCEL",
                        "request": request.model_dump(mode="json"),
                    }
                ),
                env=env,
                timeout=5,
                capture_output=True,
                text=True,
            )
            raw = json.loads(result.stdout)
            if not result.returncode and raw["status"] == "OBSERVED":
                order = raw["order"]
                raw_json = json.dumps(order, sort_keys=True, separators=(",", ":"))
                if len(raw_json) > 2_000_000:
                    raw_json = None
                    raise ValueError("oversized cancellation receipt")
                if (
                    order.get("origClientOrderId", order.get("clientOrderId")),
                    order.get("symbol"),
                ) == (request.client_order_id, request.symbol):
                    outcome = "OBSERVED"
        except Exception:
            pass
        return CancellationReceipt.model_validate(
            {
                "execution_request_id": request.execution_request_id,
                "cancellation_request_id": record.request.request_id,
                "tenant_id": request.tenant_id,
                "actor_id": record.context.actor_id,
                "client_order_id": request.client_order_id,
                "authorization_record_sha256": digest(canonical(record)),
                "outcome": outcome,
                "raw_json": raw_json,
                "observed_at": now,
            }
        )

    def quote_fills(
        self,
        request: ExecutionRequest,
        observation: VenueOrderObservation,
        receipt: VenueRuleReceipt,
        now: datetime,
    ) -> VenueQuoteFillBatch:
        receipt = VenueRuleReceipt.model_validate(receipt.model_dump())
        legacy = self.fills(request, observation, now)
        base = legacy.model_dump() | {
            "venue_rule_receipt": receipt,
            "available": False,
            "complete": False,
            "fills": (),
        }
        try:
            if legacy.raw_json is None:
                raise ValueError("SDK quote source unavailable")
            rows = json.loads(legacy.raw_json)
            entries = []
            for row in rows:
                scope = digest(
                    json.dumps(
                        [request.tenant_id, request.venue_account_ref, request.symbol, row["id"]],
                        separators=(",", ":"),
                    )
                )
                fill = Fill(
                    fill_id="fill:" + scope,
                    venue_fill_id="vfill:" + scope,
                    order_id=request.order_id,
                    quantity=row["qty"],
                    price=row["price"],
                    fee_amount=row["commission"],
                    fee_asset=row["commissionAsset"],
                    timestamp=datetime(1970, 1, 1, tzinfo=UTC)
                    + timedelta(milliseconds=row["time"]),
                )
                identity = QuoteFillIdentity(
                    tenant_id=request.tenant_id,
                    venue_account_ref=request.venue_account_ref,
                    execution_request_id=request.execution_request_id,
                    client_order_id=request.client_order_id,
                    venue_order_id=observation.venue_order_id,
                    symbol=request.symbol,
                    side=request.side,
                    raw_trade_id=row["id"],
                    fill=fill,
                )
                entries.append(
                    VenueQuoteFill(
                        identity=identity,
                        quote_quantity=row["quoteQty"],
                        quote_precision=receipt.rules.quote_precision,
                        venue_rule_receipt_sha256=digest(canonical(receipt)),
                        raw_trade_json=json.dumps(row, sort_keys=True, separators=(",", ":")),
                    )
                )
            return VenueQuoteFillBatch.model_validate(
                base
                | {
                    "available": True,
                    "complete": len(rows) < 1000,
                    "fills": tuple(entries),
                }
            )
        except Exception:
            return VenueQuoteFillBatch.model_validate(base)
