"""Run real dependencies on loopback only; cleanup all disposable test resources."""

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

# Reuse exact candidate image digests and managed-socket selector.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra/spikes"))
from platform_probe import IMAGES, docker  # noqa: E402


def main() -> None:
    prefix = "ct-integration-" + uuid.uuid4().hex[:8]
    names = [prefix + "-postgres", prefix + "-nats"]
    try:
        docker(
            "run",
            "-d",
            "--name",
            names[0],
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "-p",
            "127.0.0.1::5432",
            IMAGES["postgres"],
        )
        docker(
            "run",
            "-d",
            "--name",
            names[1],
            "-p",
            "127.0.0.1::4222",
            IMAGES["nats"],
            "-js",
            "-sd",
            "/data",
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if (
                docker("exec", names[0], "pg_isready", "-U", "postgres", check=False).returncode
                == 0
            ):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("PostgreSQL test fixture not ready")
        pg_port = docker("port", names[0], "5432/tcp").stdout.strip().rsplit(":", 1)[1]
        nats_port = docker("port", names[1], "4222/tcp").stdout.strip().rsplit(":", 1)[1]
        env = dict(os.environ)
        env["CT_TEST_DSN"] = f"postgresql://postgres@127.0.0.1:{pg_port}/postgres"
        env["CT_TEST_NATS_URL"] = f"nats://127.0.0.1:{nats_port}"
        subprocess.run(
            [sys.executable, "-m", "pytest", "tests/platform", "tests/ledger", "-q", "--tb=short"],
            env=env,
            check=True,
        )
        print("real PostgreSQL/NATS platform integration PASS")
    finally:
        for name in reversed(names):
            docker("rm", "-fv", name, check=False)


if __name__ == "__main__":
    main()
