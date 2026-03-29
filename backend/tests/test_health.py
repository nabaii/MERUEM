def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "Meruem"


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
