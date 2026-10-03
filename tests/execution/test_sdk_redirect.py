"""Actual mature SDK must not follow an untrusted fixture redirect."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from crazytrader_execution.fixture_transport import SDKFixtureTransport

from .test_states import NOW, request


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
        observation = transport.submit(request(), NOW)
        assert observation.status == "UNKNOWN"
        assert calls == ["original-fixture"]
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)
