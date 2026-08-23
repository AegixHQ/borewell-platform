def _register_and_login(client, email, role):
    register_payload = {"email": email, "password": "supersecret123", "role": role}
    client.post("/v1/auth/register", json=register_payload)
    login_payload = {"email": email, "password": "supersecret123"}
    resp = client.post("/v1/auth/login", json=login_payload)
    return resp.json()["access_token"]


def test_customer_can_create_job(client):
    token = _register_and_login(client, "cust1@example.com", "customer")
    resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.0827, "lng": 80.2707}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "lead"
    assert body["job_type"] == "residential"


def test_contractor_cannot_create_job(client):
    token = _register_and_login(client, "contractor1@example.com", "contractor")
    resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.0827, "lng": 80.2707}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_null_island_location_rejected(client):
    token = _register_and_login(client, "cust2@example.com", "customer")
    resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 0, "lng": 0}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_invalid_job_type_rejected(client):
    token = _register_and_login(client, "cust3@example.com", "customer")
    resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.0827, "lng": 80.2707}, "job_type": "spaceship"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_customer_can_only_see_own_jobs(client):
    token1 = _register_and_login(client, "custA@example.com", "customer")
    token2 = _register_and_login(client, "custB@example.com", "customer")
    client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.0827, "lng": 80.2707}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    resp = client.get("/v1/jobs", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_contractor_can_advance_job_status_sequentially(client):
    cust_token = _register_and_login(client, "custC@example.com", "customer")
    contractor_token = _register_and_login(client, "contractorC@example.com", "contractor")

    create_resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.0827, "lng": 80.2707}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    job_id = create_resp.json()["job_id"]

    advance_resp = client.patch(
        f"/v1/jobs/{job_id}/status",
        json={"status": "site_location"},
        headers={"Authorization": f"Bearer {contractor_token}"},
    )
    assert advance_resp.status_code == 200
    assert advance_resp.json()["status"] == "site_location"


def test_skipping_a_status_is_rejected(client):
    cust_token = _register_and_login(client, "custD@example.com", "customer")
    contractor_token = _register_and_login(client, "contractorD@example.com", "contractor")

    create_resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.0827, "lng": 80.2707}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    job_id = create_resp.json()["job_id"]

    resp = client.patch(
        f"/v1/jobs/{job_id}/status",
        json={"status": "booking"},  # skips several states ahead
        headers={"Authorization": f"Bearer {contractor_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_TRANSITION"


def test_customer_cannot_advance_job_status(client):
    cust_token = _register_and_login(client, "custE@example.com", "customer")
    create_resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.0827, "lng": 80.2707}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    job_id = create_resp.json()["job_id"]

    resp = client.patch(
        f"/v1/jobs/{job_id}/status",
        json={"status": "site_location"},
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert resp.status_code == 403
