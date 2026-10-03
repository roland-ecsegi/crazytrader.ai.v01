"""Actual mature SDK must not follow an untrusted fixture redirect."""

import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from crazytrader_execution.fixture_transport import SDKFixtureTransport

from .test_states import request


def test_fixed_fixture_sdk_does_not_follow_redirect():
    calls = []

    class Target(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append("redirect-followed")
            self.send_response(200)
            self.end_headers()

    target = ThreadingHTTPServer(("127.0.0.1", 0), Target)

    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            calls.append("original-fixture")
            self.send_response(301)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/")
            self.send_header("Content-Length", "0")
            self.end_headers()

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    servers = (target, origin)
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in servers]
    for thread in threads:
        thread.start()
    root = Path(__file__).resolve().parents[2]
    try:
        transport = SDKFixtureTransport(
            f"http://127.0.0.1:{origin.server_port}",
            root / "services/market-data/sdk/.venv/bin/python",
            root / "services/execution/sdk_fixture_transport.py",
        )
        now = datetime.now(UTC)
        current = type(request()).model_validate(
            request().model_dump()
            | {
                "created_at": now,
                "expires_at": now + timedelta(seconds=5),
            }
        )
        observation = transport.submit(current, now)
        assert observation.status == "UNKNOWN"
        assert calls == ["original-fixture"]
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)


def test_fixed_child_never_loads_injected_dummy_netrc_auth(tmp_path):
    import json
    import os
    import subprocess

    root = Path(__file__).resolve().parents[2]
    seen = []

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append(self.headers.get("Authorization"))
            body = b'{"code":-2013,"msg":"Order does not exist."}'
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    netrc = tmp_path / "dummy-netrc"
    netrc.write_text("machine 127.0.0.1 login fixture-test-only password fixture-test-only\n")
    netrc.chmod(0o600)
    try:
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT"}}
        env["NETRC"] = str(netrc)
        response = subprocess.run(
            [
                str(root / "services/market-data/sdk/.venv/bin/python"),
                str(root / "services/execution/sdk_fixture_transport.py"),
            ],
            input=json.dumps(
                {
                    "endpoint": f"http://127.0.0.1:{server.server_port}",
                    "action": "LOOKUP",
                    "request": request().model_dump(mode="json"),
                }
            ),
            env=env,
            text=True,
            capture_output=True,
            timeout=5,
        )
        assert response.returncode == 0
        assert json.loads(response.stdout)["status"] == "OBSERVED"
        assert seen == [None]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
