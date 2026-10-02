"""Disposable local platform probes. No secrets, exchange or host ingress."""

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

IMAGES = {
    "postgres": (
        "postgres:17.6-bookworm@sha256:"
        "f3bd19c606e442c3d7bdfa8002e03fe260a1023351e0ea4598032022b68dd6e3"
    ),
    "nats": (
        "nats:2.11.8-alpine@sha256:71092f77d707a4a81b12aca5096d6b2d2e07ad16aa57c84066940a17af74f61a"
    ),
    "opa": (
        "openpolicyagent/opa:1.8.0@sha256:"
        "0917dda453560b65798d3c78caed0376c4db0708f1e4df5724058a5dfd412948"
    ),
    "openbao": (
        "openbao/openbao:2.3.2@sha256:"
        "afec9f65a7067a22acf24b29f07d2f028353c02cc0fa9c80dfa4e7fab158b373"
    ),
    "clickhouse": (
        "clickhouse/clickhouse-server:25.8.3.66@sha256:"
        "3b28daecdf0625bd7dc27d555ae8f39042882045e49b04668ceccdd282f67d9b"
    ),
    "mlflow": (
        "ghcr.io/mlflow/mlflow:v3.4.0@sha256:"
        "9c9e24a3fc24a0e9dcc5ba1daa9ebfc59e01b0a23b6eb89a4fdf25b84ad5347c"
    ),
    "object": (
        "chrislusf/seaweedfs:3.97@sha256:"
        "bb05d66d2963b1cc48073190781c3dd29e2c4c88a2ae2986bf58e38c86d89c6e"
    ),
}
# Retain configured client registry/proxy/CA trust, select only managed socket.
ENV = {
    k: v
    for k, v in os.environ.items()
    if k
    not in {"DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}
}


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "--host=unix:///var/run/docker.sock", *args],
        env=ENV,
        text=True,
        capture_output=True,
        check=check,
        timeout=60,
    )


def wait_exec(name: str, *args: str) -> str:
    end = time.monotonic() + 45
    while time.monotonic() < end:
        result = docker("exec", name, *args, check=False)
        if result.returncode == 0:
            return result.stdout.strip()
        time.sleep(0.5)
    raise RuntimeError(f"local readiness failed: {name}: {result.stderr}")


def main() -> None:
    prefix = "ct-spike-" + uuid.uuid4().hex[:8]
    network = prefix + "-network"
    containers: list[str] = []
    volumes: list[str] = []
    observed = {}
    docker("network", "create", "--internal", network)

    def start(key: str, args: list[str], options: list[str] | None = None) -> str:
        name = prefix + "-" + key
        containers.append(name)
        docker(
            "run",
            "-d",
            "--name",
            name,
            "--network",
            network,
            "--network-alias",
            key,
            "--label",
            "crazytrader.spike=true",
            *(options or []),
            IMAGES[key],
            *args,
        )
        return name

    try:
        volume = prefix + "-postgres-data"
        docker("volume", "create", volume)
        volumes.append(volume)
        pg = start(
            "postgres",
            [],
            ["-e", "POSTGRES_HOST_AUTH_METHOD=trust", "-v", volume + ":/var/lib/postgresql/data"],
        )
        wait_exec(pg, "pg_isready", "-U", "postgres")
        sql = (
            "CREATE TABLE spike(id text PRIMARY KEY, amount numeric(38,18)); "
            "INSERT INTO spike VALUES ('once', 0.1);"
        )
        docker("exec", pg, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-c", sql)
        docker("restart", pg)
        wait_exec(pg, "pg_isready", "-U", "postgres")
        value = docker(
            "exec", pg, "psql", "-U", "postgres", "-Atc", "SELECT amount FROM spike WHERE id='once'"
        ).stdout.strip()
        assert value == "0.100000000000000000"
        print("PostgreSQL restart probe PASS", flush=True)
        observed["postgres"] = {
            "restart_decimal_persistence": value,
            "fixture_auth": "trust/internal disposable only",
        }
        nats = start("nats", ["-js", "-m", "8222", "-sd", "/data"])
        js = json.loads(wait_exec(nats, "wget", "-Y", "off", "-qO-", "http://127.0.0.1:8222/jsz"))
        assert js["config"]["store_dir"] == "/data/jetstream"
        observed["nats"] = {
            "jetstream_enabled": True,
            "version": json.loads(
                docker(
                    "exec", nats, "wget", "-Y", "off", "-qO-", "http://127.0.0.1:8222/varz"
                ).stdout
            )["version"],
        }
        print("NATS JetStream probe PASS", flush=True)
        observed["opa"] = docker(
            "run", "--rm", "--network", "none", IMAGES["opa"], "eval", "--format=values", "false"
        ).stdout.strip()
        assert observed["opa"] == "[\n  false\n]"
        config = Path(__file__).with_name("openbao-spike.hcl")
        bao = prefix + "-openbao"
        containers.append(bao)
        docker(
            "create",
            "--name",
            bao,
            "--network",
            network,
            "--cap-drop=ALL",
            "--user",
            "1000:1000",
            "--entrypoint",
            "bao",
            IMAGES["openbao"],
            "server",
            "-config=/tmp/spike.hcl",
        )
        docker("cp", str(config), bao + ":/tmp/spike.hcl")
        docker("start", bao)
        end = time.monotonic() + 30
        while time.monotonic() < end:
            result = docker(
                "exec",
                "-e",
                "NO_PROXY=127.0.0.1",
                bao,
                "bao",
                "status",
                "-address=http://127.0.0.1:8200",
                "-format=json",
                check=False,
            )
            if result.returncode == 2 and result.stdout.startswith("{"):
                status = json.loads(result.stdout)
                assert not status["initialized"] and status["sealed"]
                observed["openbao"] = {
                    "initialized": False,
                    "sealed": True,
                    "version": status["version"],
                }
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("OpenBao uninitialized probe failed: " + docker("logs", bao).stderr)
        ch = start("clickhouse", [])
        observed["clickhouse"] = wait_exec(
            ch, "clickhouse-client", "--query", "SELECT version(), toDecimal128('0.1',18)"
        )
        assert "0.1" in observed["clickhouse"]
        ml = start("mlflow", ["-c", "sleep 300"], ["--entrypoint", "sh"])
        # Override sh command: run a temporary process with no inbound server.
        registry = """
from mlflow import MlflowClient
import mlflow
c = MlflowClient('file:///tmp/mlruns')
e = c.create_experiment('compatibility')
r = c.create_run(e)
c.log_param(r.info.run_id, 'dataset', 'fixture-v1')
assert c.get_run(r.info.run_id).data.params['dataset'] == 'fixture-v1'
print(mlflow.__version__)
"""
        observed["mlflow"] = docker("exec", ml, "python", "-c", registry).stdout.strip()
        obj = start(
            "object", ["server", "-s3", "-dir=/data", "-ip=object"],
            ["-e", "NO_PROXY=object,127.0.0.1", "-e", "no_proxy=object,127.0.0.1"],
        )
        probe = """
import requests
s = requests.Session()
s.trust_env = False  # declared isolated local service, never external egress
u = 'http://object:8333/spike'
s.put(u, timeout=3).raise_for_status()
s.put(u + '/fixture', data=b'fixture-v1', timeout=3).raise_for_status()
assert s.get(u + '/fixture', timeout=3).content == b'fixture-v1'
print('S3 PUT/GET fixture PASS')
"""
        try:
            observed["object"] = wait_exec(ml, "python", "-c", probe)
        except Exception:
            print(docker("logs", obj).stderr[-4000:], flush=True)
            raise
        evidence = {
            "images": IMAGES,
            "observed": observed,
            "limitations": [
                "spike data only",
                "no production authentication/TLS validation",
                "no NATS consumer replay test yet",
                "no OpenBao initialization or secrets",
                "no exchange calls",
                "MLflow fixture file backend only",
            ],
            "certification": "L0",
        }
        (
            Path(__file__).resolve().parents[2] / "docs/evidence/spikes/platform-compatibility.json"
        ).write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        print("local platform compatibility PASS")
    finally:
        for name in reversed(containers):
            docker("rm", "-f", name, check=False)
        for name in volumes:
            docker("volume", "rm", name, check=False)
        docker("network", "rm", network, check=False)


if __name__ == "__main__":
    main()
