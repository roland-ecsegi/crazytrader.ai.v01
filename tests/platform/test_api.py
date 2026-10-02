from crazytrader_platform.control import ControlAPI
from crazytrader_platform.storage import EventStore
from fastapi.testclient import TestClient

TOKEN = "local-test-fixture-" + "x" * 32


async def broker_down() -> bool:
    raise RuntimeError("sensitive-connection-error-sentinel")


def test_read_only_api_auth_and_redaction_under_dependency_failure() -> None:
    api = ControlAPI(EventStore("postgresql://postgres@127.0.0.1:1/postgres"), broker_down, TOKEN)
    with TestClient(api.app) as client:
        assert client.get("/live").json() == {"status": "alive"}
        for path in ("/ready", "/metrics", "/certification"):
            assert client.get(path).status_code == 401
            assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
        headers = {"Authorization": "Bearer " + TOKEN}
        response = client.get("/ready", headers=headers)
        assert response.status_code == 503
        assert "sensitive" not in response.text and "postgresql" not in response.text
        assert TOKEN not in response.text
        assert client.get("/certification", headers=headers).json()["live_activation"] == "DISABLED"
        assert "ct_auth_denials_total 6.0" in client.get("/metrics", headers=headers).text
        assert client.post("/orders", headers=headers, json={}).status_code == 404
