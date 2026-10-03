"""Version-bound mature OPA client; invalid/outage/identity changes never authorize."""

import hashlib
import json
import os
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

import httpx
from crazytrader_contracts.models import (
    Contract,
    Identifier,
    PolicyDecision,
    Timestamp,
    TradeIntent,
)
from crazytrader_contracts.risk import RiskAuthorization, RiskContext
from crazytrader_platform.storage import canonical, digest
from pydantic import Field

from .engine import evaluate


class PolicyReply(Contract):
    allow: Annotated[bool, Field(strict=True)]
    reason_codes: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    policy_bundle_sha256: str
    policy_version: Literal["spot-policy.v1"]
    risk_decision_id: Identifier
    intent_sha256: str
    context_sha256: str
    tenant_id: Identifier
    actor_id: Identifier


class PolicyResult(Contract):
    decision: PolicyDecision
    risk_authorization: RiskAuthorization
    policy_bundle_sha256: str
    evaluated_at: Timestamp
    expires_at: Timestamp


def request(
    intent: TradeIntent,
    context: RiskContext,
    authorization: RiskAuthorization,
    now: datetime,
    permissions: tuple[str, ...],
    symbols: tuple[str, ...],
    policy_hash: str,
) -> dict[str, object]:
    # A forged ALLOW or copied/changed authorization must not enter policy evaluation.
    if authorization != evaluate(intent, context, authorization.evaluated_at):
        raise ValueError("risk authorization is not bound to exact intent/state")
    return {
        "schema_version": "1",
        "intent_json": canonical(intent),
        "context_json": canonical(context),
        "authorization": authorization.model_dump(mode="json"),
        "now": now.isoformat(),
        "tenant_id": context.tenant_id,
        "actor_id": context.actor_id,
        "actor_permissions": permissions,
        "symbol_allowlist": symbols,
        "policy_bundle_sha256": policy_hash,
    }


class OPAClient:
    def __init__(self, endpoint: str, policy_path: Path) -> None:
        self.endpoint = endpoint.rstrip("/") + "/v1/data/crazytrader/authorization/decision"
        self.policy_hash = digest(policy_path.read_text())

    def _evaluate_body(self, body: dict[str, object]) -> object:
        with httpx.Client(timeout=httpx.Timeout(2.0), follow_redirects=False) as client:
            response = client.post(self.endpoint, json={"input": body})
            response.raise_for_status()
            return response.json()

    def authorize(
        self,
        intent: TradeIntent,
        context: RiskContext,
        authorization: RiskAuthorization,
        now: datetime,
        permissions: tuple[str, ...],
        symbols: tuple[str, ...],
    ) -> PolicyResult:
        reason = "POLICY_UNAVAILABLE_OR_INVALID"
        verdict = "DENY"
        try:
            body = request(
                intent, context, authorization, now, permissions, symbols, self.policy_hash
            )
            raw = self._evaluate_body(body)
            if not isinstance(raw, dict) or set(raw) != {"result"}:
                raise ValueError("invalid policy response wrapper")
            reply = PolicyReply.model_validate(raw["result"])
            if (
                reply.policy_bundle_sha256,
                reply.risk_decision_id,
                reply.intent_sha256,
                reply.context_sha256,
                reply.tenant_id,
                reply.actor_id,
            ) != (
                self.policy_hash,
                authorization.decision.risk_decision_id,
                authorization.intent_sha256,
                authorization.context_sha256,
                context.tenant_id,
                context.actor_id,
            ):
                raise ValueError("policy identity/hash mismatch")
            if (
                not authorization.evaluated_at <= now < authorization.expires_at
                or not intent.created_at <= now < intent.expires_at
            ):
                raise ValueError("expired policy request")
            verdict = "ALLOW" if reply.allow else "DENY"
            reason = reply.reason_codes[0]
        except Exception:
            pass  # deliberately deny without exposing URL/auth/raw policy exception
        key = digest(
            json.dumps(
                [
                    authorization.decision.risk_decision_id,
                    self.policy_hash,
                    now.isoformat(),
                    verdict,
                    reason,
                ]
            )
        )
        decision = PolicyDecision(
            policy_decision_id="policy:" + key,
            intent_id=intent.intent_id,
            actor_id=context.actor_id,
            decision=verdict,
            reason_codes=(reason,),
            policy_bundle_version="spot-policy.v1:" + self.policy_hash,
            created_at=now,
        )
        return PolicyResult(
            decision=decision,
            risk_authorization=authorization,
            policy_bundle_sha256=self.policy_hash,
            evaluated_at=now,
            expires_at=authorization.expires_at,
        )


class LocalReductionPolicy(OPAClient):
    """Same verified Rego with pinned local OPA; opt-in owner reduction only."""

    def __init__(
        self,
        binary: Path,
        binary_sha256: str,
        policy_path: Path,
        data_path: Path,
        enabled: bool = False,
    ) -> None:
        super().__init__("local-offline", policy_path)
        if type(enabled) is not bool:
            raise ValueError("explicit owner-local reduction opt-in required")
        self.binary, self.binary_hash = binary, binary_sha256
        self.policy_path, self.data_path, self.enabled = policy_path, data_path, enabled
        self.data_hash = digest(data_path.read_text())

    def _evaluate_body(self, body: dict[str, object]) -> object:
        authorization = body["authorization"]
        if not isinstance(authorization, dict) or not isinstance(
            authorization.get("decision"), dict
        ):
            raise ValueError("invalid reduction authorization")
        if not self.enabled or authorization["decision"].get("risk_effect") != "RISK_REDUCING":
            raise ValueError("offline policy grants no increasing authority")
        if (
            digest(self.policy_path.read_text()) != self.policy_hash
            or digest(self.data_path.read_text()) != self.data_hash
        ):
            raise ValueError("local policy bundle changed")
        with self.binary.open("rb") as binary_file:
            if hashlib.file_digest(binary_file, "sha256").hexdigest() != self.binary_hash:
                raise ValueError("local OPA binary changed")
        env = {key: value for key, value in os.environ.items() if key in {"PATH", "SYSTEMROOT"}}
        result = subprocess.run(
            [
                str(self.binary),
                "eval",
                "--format=json",
                "--stdin-input",
                "--data",
                str(self.policy_path),
                "--data",
                str(self.data_path),
                "data.crazytrader.authorization.decision",
            ],
            input=json.dumps(body),
            text=True,
            capture_output=True,
            timeout=2,
            env=env,
        )
        if result.returncode:
            raise RuntimeError("local OPA reduction policy unavailable")
        raw = json.loads(result.stdout)
        return {"result": raw["result"][0]["expressions"][0]["value"]}


class PolicyRouter:
    def __init__(
        self, remote: OPAClient, local: LocalReductionPolicy, clock: Callable[[], datetime]
    ) -> None:
        if remote.policy_hash != local.policy_hash:
            raise ValueError("remote/local approved policy versions differ")
        self.remote, self.local, self.clock = remote, local, clock

    def authorize(
        self,
        intent: TradeIntent,
        context: RiskContext,
        authorization: RiskAuthorization,
        permissions: tuple[str, ...],
        symbols: tuple[str, ...],
    ) -> PolicyResult:
        result = self.remote.authorize(
            intent, context, authorization, self.clock(), permissions, symbols
        )
        if (
            result.decision.reason_codes == ("POLICY_UNAVAILABLE_OR_INVALID",)
            and authorization.decision.risk_effect == "RISK_REDUCING"
        ):
            return self.local.authorize(
                intent, context, authorization, self.clock(), permissions, symbols
            )
        return result  # a policy DENY cannot be overturned by outage fallback
