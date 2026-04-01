from app.core.config import settings


def test_profiling_stats_route_is_mounted(client):
    response = client.get("/api/v1/profiling/stats")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_assessed"] == 0
    assert payload["persona_distribution"] == {}


def test_create_profiling_job_requires_anthropic_key(client, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    response = client.post("/api/v1/profiling/jobs", json={"filters": {}})
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]
