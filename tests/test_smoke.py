from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    with TestClient(app) as client:
        resp = client.get("/api/system/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["database"]["ok"] is True
        assert body["scheduler"]["running"] is True
        assert "counts" in body


def test_meta_has_no_secrets():
    with TestClient(app) as client:
        resp = client.get("/api/system/meta")
        assert resp.status_code == 200
        text = resp.text.lower()
        assert "api_key" not in text
        assert "secret" not in text


def test_root_serves_dashboard():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "EPIC" in resp.text


def test_jobs_endpoint():
    with TestClient(app) as client:
        resp = client.get("/api/system/jobs")
        assert resp.status_code == 200
        assert "data" in resp.json()
