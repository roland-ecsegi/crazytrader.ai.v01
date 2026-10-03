"""Exact-digest disposable market stores, loopback only, no venue credentials."""

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra/spikes"))
from platform_probe import IMAGES, docker  # noqa: E402


def main() -> None:
    prefix = "ct-market-" + uuid.uuid4().hex[:8]
    names = [prefix + "-" + key for key in ("postgres", "clickhouse", "object")]
    network = prefix + "-network"
    docker("network", "create", network)
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
            "-e",
            "CLICKHOUSE_USER=fixture",
            "-e",
            "CLICKHOUSE_PASSWORD=fixture",
            "-e",
            "CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1",
            "-p",
            "127.0.0.1::8123",
            IMAGES["clickhouse"],
        )
        docker(
            "run",
            "-d",
            "--name",
            names[2],
            "--network",
            network,
            "--network-alias",
            "object",
            "-e",
            "NO_PROXY=object,127.0.0.1,localhost",
            "-e",
            "no_proxy=object,127.0.0.1,localhost",
            "-p",
            "127.0.0.1::8333",
            IMAGES["object"],
            "server",
            "-s3",
            "-master.volumeSizeLimitMB=16",
            "-volume.max=4",
            "-dir=/data",
            "-ip=object",
        )
        ports = [
            docker("port", n, p).stdout.strip().rsplit(":", 1)[1]
            for n, p in zip(names, ("5432/tcp", "8123/tcp", "8333/tcp"), strict=True)
        ]
        env = dict(os.environ)
        env.update(
            CT_TEST_DSN=f"postgresql://postgres@127.0.0.1:{ports[0]}/postgres",
            CT_TEST_CH_PORT=ports[1],
            CT_TEST_CH_CONTAINER=names[1],
            CT_TEST_S3=f"http://127.0.0.1:{ports[2]}",
        )
        env["NO_PROXY"] = env.get("NO_PROXY", "") + ",127.0.0.1,localhost"
        env["no_proxy"] = env["NO_PROXY"]
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            pg = docker("exec", names[0], "pg_isready", "-U", "postgres", check=False)
            ch = docker(
                "exec",
                names[1],
                "clickhouse-client",
                "--user",
                "fixture",
                "--password",
                "fixture",
                "--query",
                "SELECT 1",
                check=False,
            )
            s3 = docker(
                "exec", names[2], "wget", "-Y", "off", "-qO-", "http://127.0.0.1:8333", check=False
            )
            if pg.returncode == ch.returncode == s3.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("market fixtures not ready")
        subprocess.run(
            [sys.executable, "-m", "pytest", "tests/market", "-q", "--tb=short"],
            env=env,
            check=True,
        )
        print("real PostgreSQL/ClickHouse/S3 market integration PASS")
    except Exception:
        for name in names:
            logs = docker("logs", "--tail", "12", name, check=False)
            print(logs.stdout[-1500:] + logs.stderr[-1500:])
        raise
    finally:
        for name in reversed(names):
            docker("rm", "-fv", name, check=False)
        docker("network", "rm", network, check=False)


if __name__ == "__main__":
    main()
