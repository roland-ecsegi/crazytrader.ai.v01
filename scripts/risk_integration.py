"""Pinned actual OPA HTTP policy test; unsigned internal authorization only."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx
from crazytrader_platform.storage import digest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra/spikes"))
from platform_probe import IMAGES, docker  # noqa: E402


def main() -> None:
    name = "ct-risk-" + uuid.uuid4().hex[:8]
    policy = Path("infra/policy/authorization.rego")
    with tempfile.TemporaryDirectory(prefix="ct-risk-bundle-") as directory:
        data = Path(directory) / "bundle.json"
        data.write_text(
            json.dumps(
                {
                    "bundle": {
                        "version": "spot-policy.v1",
                        "policy_sha256": digest(policy.read_text()),
                    }
                }
            )
        )
        data.chmod(0o644)
        policy.chmod(0o644)
        try:
            docker(
                "create",
                "--name",
                name,
                "-p",
                "127.0.0.1::8181",
                IMAGES["opa"],
                "run",
                "--server",
                "--addr=0.0.0.0:8181",
                "/policy.rego",
                "/bundle.json",
            )
            docker("cp", str(policy), name + ":/policy.rego")
            docker("cp", str(data), name + ":/bundle.json")
            docker("cp", name + ":/opa", str(Path(directory) / "opa"))
            binary = Path(directory) / "opa"
            binary.chmod(0o755)
            with binary.open("rb") as f:
                binary_hash = hashlib.file_digest(f, "sha256").hexdigest()
            docker("start", name)
            port = docker("port", name, "8181/tcp").stdout.strip().rsplit(":", 1)[1]
            endpoint = f"http://127.0.0.1:{port}"
            env = dict(os.environ)
            env["CT_TEST_OPA_URL"] = endpoint
            env["CT_TEST_OPA_BINARY"] = str(binary)
            env["CT_TEST_OPA_BINARY_SHA256"] = binary_hash
            env["CT_TEST_OPA_DATA"] = str(data)
            env["NO_PROXY"] = env.get("NO_PROXY", "") + ",127.0.0.1,localhost"
            env["no_proxy"] = env["NO_PROXY"]
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    httpx.get(endpoint + "/health", timeout=1, trust_env=False).raise_for_status()
                    break
                except httpx.HTTPError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("OPA fixture not ready")
            subprocess.run(
                [sys.executable, "-m", "pytest", "tests/risk", "-q", "--tb=short"],
                env=env,
                check=True,
            )
            print("actual OPA bound risk/permission/expiry/reduction integration PASS")
        except Exception:
            result = docker("logs", "--tail", "15", name, check=False)
            print(result.stdout[-2500:] + result.stderr[-2500:])
            raise
        finally:
            docker("rm", "-fv", name, check=False)


if __name__ == "__main__":
    main()
