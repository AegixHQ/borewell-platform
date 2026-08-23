def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz(client):
    # Exercises the real DB check (SELECT 1) against the test SQLite DB.
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
