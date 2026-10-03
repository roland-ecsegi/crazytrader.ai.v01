"""Credential-free isolated native simulation result transport; no venue adapter."""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from crazytrader_contracts.codec import canonical, digest
from crazytrader_contracts.simulation import NativeSimulationJob, NativeSimulationReceipt


class NativeSimulationTransport:
    def __init__(
        self, python: Path, worker: Path, contract_source: Path, result_root: Path
    ) -> None:
        self.python, self.worker, self.contract_source = python, worker, contract_source
        self.result_root = result_root.resolve()
        self.result_root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def recover_result(self, job: NativeSimulationJob) -> NativeSimulationReceipt | None:
        job = NativeSimulationJob.model_validate(job.model_dump())
        path = self.result_root / (digest(canonical(job)) + ".json")
        if not path.exists():
            return None
        if path.stat().st_size > 2_500_000:
            raise ValueError("native result exceeds bounded source")
        receipt = NativeSimulationReceipt.model_validate_json(path.read_text())
        if receipt.job != job:
            raise ValueError("native result immutable job mismatch")
        return receipt

    def simulate(
        self, job: NativeSimulationJob, *, interrupt_after_result: bool = False
    ) -> NativeSimulationReceipt:
        job = NativeSimulationJob.model_validate(job.model_dump())
        existing = self.recover_result(job)
        if existing is not None:
            return existing
        claim = self.result_root / (digest(canonical(job)) + ".claimed")
        try:
            descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return NativeSimulationReceipt(
                job=job,
                job_sha256=digest(canonical(job)),
                observed_at=datetime.now(UTC),
                available=False,
                raw_json=None,
            )
        with os.fdopen(descriptor, "w") as output:
            output.write(canonical(job))
            output.flush()
            os.fsync(output.fileno())
        directory = os.open(self.result_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        env = {key: value for key, value in os.environ.items() if key in {"PATH", "SYSTEMROOT"}}
        env.update(
            PYTHONPATH=str(self.contract_source),
            NO_PROXY="127.0.0.1,localhost",
            no_proxy="127.0.0.1,localhost",
        )
        try:
            subprocess.run(
                [str(self.python), str(self.worker)],
                env=env,
                input=json.dumps(
                    {
                        "job": job.model_dump(mode="json"),
                        "result_root": str(self.result_root),
                        "interrupt_after_result": interrupt_after_result,
                    }
                ),
                timeout=10,
                capture_output=True,
                text=True,
            )
        except Exception:
            pass  # no URL/environment/error text forwarded; persisted result decides recovery
        existing = self.recover_result(job)
        if existing is not None:
            return existing
        return NativeSimulationReceipt(
            job=job,
            job_sha256=digest(canonical(job)),
            observed_at=datetime.now(UTC),
            available=False,
            raw_json=None,
        )
