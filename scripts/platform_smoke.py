"""Actual non-root Compose runtime smoke with disposable owner-token fixtures."""

import json
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra/spikes"))
from platform_probe import ENV  # noqa: E402


def main() -> None:
    project = "ct-smoke-" + uuid.uuid4().hex[:8]
    token = secrets.token_urlsafe(40)
    password = secrets.token_hex(24)
    env = dict(ENV)
    env.update(
        CT_POSTGRES_PASSWORD=password,
        CT_DATABASE_DSN=f"postgresql://crazytrader:{password}@postgres/crazytrader",
        CT_OWNER_TOKEN=token,
        CT_CONTROL_PORT="0",
    )
    command = [
        "docker",
        "--host=unix:///var/run/docker.sock",
        "compose",
        "-p",
        project,
        "-f",
        "infra/compose.platform.yml",
    ]

    def compose(*args: str) -> str:
        result = subprocess.run(
            command + list(args), env=env, capture_output=True, text=True, timeout=60
        )
        if result.returncode:
            # Suppress runtime config/errors which could include fixture credentials.
            raise RuntimeError("Compose smoke command failed: " + args[0])
        return result.stdout.strip()

    # Only this explicitly loopback URL bypasses external proxy routing.
    local_http = build_opener(ProxyHandler({}))
    try:
        compose("config", "--quiet")
        compose("up", "-d", "postgres", "nats")
        compose("run", "--rm", "migrate")
        compose("up", "-d", "outbox", "audit", "notification", "control-api")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                port = compose("port", "control-api", "8080").rsplit(":", 1)[1]
                break
            except (RuntimeError, IndexError):
                time.sleep(0.5)
        else:
            logs = compose("logs", "--no-color", "control-api")
            logs = logs.replace(token, "[fixture-token]").replace(password, "[fixture-password]")
            print(logs[-3000:])
            raise RuntimeError("control API container did not stay running")
        base = "http://127.0.0.1:" + port

        def status(path: str, authenticated: bool = True) -> tuple[int, dict[str, object]]:
            request = Request(
                base + path, headers={"Authorization": "Bearer " + token} if authenticated else {}
            )
            try:
                with local_http.open(request, timeout=2) as response:
                    return response.status, json.loads(response.read())
            except HTTPError as exc:
                return exc.code, json.loads(exc.read())

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if status("/ready")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("actual platform workers never became ready")
        assert compose("exec", "-T", "notification", "id", "-u") == "10001"
        assert status("/ready", False)[0] == 401
        assert status("/certification")[1]["level"] == "L0"
        compose("stop", "audit")
        time.sleep(5.2)
        assert status("/ready")[0] == 503
        compose("start", "audit")
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if status("/ready")[0] == 200:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("worker did not recover after restart")
        print("actual Compose runtime/auth/worker-stop/restart smoke PASS")
        Path("docs/evidence/platform-runtime.json").write_text(
            json.dumps(
                {
                    "certification": "L0",
                    "checks": [
                        "actual non-root image build",
                        "explicit migration",
                        "three worker readiness",
                        "owner authentication",
                        "audit worker stop -> degraded",
                        "audit worker restart -> ready",
                    ],
                    "secrets": "random disposable platform fixtures only; never recorded",
                    "limitations": [
                        "development service credentials",
                        "no production TLS/role isolation",
                        "no financial execution",
                        "no live readiness claim",
                    ],
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        subprocess.run(
            command + ["down", "-v", "--remove-orphans"], env=env, capture_output=True, timeout=60
        )


if __name__ == "__main__":
    main()
