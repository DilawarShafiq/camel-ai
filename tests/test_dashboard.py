"""Dashboard app tests via Starlette's TestClient — no live server needed."""

from starlette.testclient import TestClient

from camel.dashboard import app

client = TestClient(app)


def test_home_serves_ui():
    r = client.get("/")
    assert r.status_code == 200
    assert "Camel AI" in r.text
    assert "Run audit" in r.text


def test_status_endpoint_shape():
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "brain" in data and "configured" in data and "platform" in data


def test_audit_requires_url():
    r = client.post("/api/audit", json={"url": ""})
    assert r.status_code == 400
    assert "error" in r.json()


def test_see_endpoint_shape():
    r = client.get("/api/see")
    assert r.status_code == 200
    data = r.json()
    assert "windows" in data and isinstance(data["windows"], list)
