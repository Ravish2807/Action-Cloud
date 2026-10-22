from fastapi.testclient import TestClient


def test_prometheus_endpoint_requires_configured_bearer_token(monkeypatch):
    from actioncloud import api
    from actioncloud.config import settings

    monkeypatch.setattr(settings, "prometheus_metrics_token", "test-metrics-secret")
    client = TestClient(api.app)

    assert client.get("/metrics/prometheus").status_code == 401
    assert client.get(
        "/metrics/prometheus", headers={"Authorization": "Bearer incorrect"}
    ).status_code == 401
    response = client.get(
        "/metrics/prometheus", headers={"Authorization": "Bearer test-metrics-secret"}
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_prometheus_endpoint_remains_available_without_token(monkeypatch):
    from actioncloud import api
    from actioncloud.config import settings

    monkeypatch.setattr(settings, "prometheus_metrics_token", None)
    response = TestClient(api.app).get("/metrics/prometheus")
    assert response.status_code == 200
