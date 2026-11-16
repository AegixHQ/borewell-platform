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

    # SRS section 11 acceptance criterion, verbatim: "...returns an error
    # AND the job's status is unchanged" - a 400 alone doesn't prove the
    # row wasn't mutated before the error was raised. Re-fetch and check.
    get_resp = client.get(
        f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {contractor_token}"}
    )
    assert get_resp.json()["status"] == "lead"


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


# ---------- walk-in jobs ----------

WALK_IN = {
    "customer_name": "  Ramesh   Kumar ",
    "customer_phone": "+91 98765-43210",
    "location": {"lat": 13.0827, "lng": 80.2707},
    "job_type": "agricultural",
}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_contractor_can_open_a_walk_in_job(client):
    token = _register_and_login(client, "wi-contractor@example.com", "contractor")
    resp = client.post("/v1/jobs/walk-in", json=WALK_IN, headers=_auth(token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["walk_in"] is True
    assert body["status"] == "lead"
    assert body["customer_name"] == "Ramesh Kumar"  # whitespace tidied
    assert body["customer_phone"] == "9876543210"  # normalised to 10 digits
    assert body["customer_id"]


def test_walk_in_customer_ids_are_fresh_each_time(client):
    token = _register_and_login(client, "wi-contractor2@example.com", "contractor")
    a = client.post("/v1/jobs/walk-in", json=WALK_IN, headers=_auth(token)).json()
    b = client.post("/v1/jobs/walk-in", json=WALK_IN, headers=_auth(token)).json()
    assert a["customer_id"] != b["customer_id"]


def test_customer_cannot_open_a_walk_in_job(client):
    token = _register_and_login(client, "wi-cust@example.com", "customer")
    assert client.post("/v1/jobs/walk-in", json=WALK_IN, headers=_auth(token)).status_code == 403


def test_resource_owner_cannot_open_a_walk_in_job(client):
    token = _register_and_login(client, "wi-owner@example.com", "resource_owner")
    assert client.post("/v1/jobs/walk-in", json=WALK_IN, headers=_auth(token)).status_code == 403


def test_walk_in_requires_a_token(client):
    assert client.post("/v1/jobs/walk-in", json=WALK_IN).status_code == 401


def test_walk_in_job_is_invisible_to_app_customers_but_listed_for_contractors(client):
    contractor = _register_and_login(client, "wi-contractor3@example.com", "contractor")
    customer = _register_and_login(client, "wi-cust2@example.com", "customer")
    job = client.post("/v1/jobs/walk-in", json=WALK_IN, headers=_auth(contractor)).json()

    assert client.get("/v1/jobs", headers=_auth(customer)).json() == []
    assert client.get(f"/v1/jobs/{job['job_id']}", headers=_auth(customer)).status_code == 403
    listed = client.get("/v1/jobs", headers=_auth(contractor)).json()
    assert [j["job_id"] for j in listed] == [job["job_id"]]
    assert listed[0]["walk_in"] is True


def test_normal_jobs_are_not_walk_ins(client):
    token = _register_and_login(client, "wi-cust3@example.com", "customer")
    resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.0827, "lng": 80.2707}, "job_type": "residential"},
        headers=_auth(token),
    )
    body = resp.json()
    assert body["walk_in"] is False
    assert body["customer_name"] is None and body["customer_phone"] is None


def test_walk_in_validation(client):
    token = _register_and_login(client, "wi-contractor4@example.com", "contractor")
    for bad in (
        {**WALK_IN, "customer_name": "   "},
        {**WALK_IN, "customer_name": "x" * 101},
        {**WALK_IN, "customer_phone": "12345"},
        {**WALK_IN, "customer_phone": "98765abcde"},
        {**WALK_IN, "job_type": "spaceship"},
        {**WALK_IN, "location": {"lat": 0, "lng": 0}},
    ):
        resp = client.post("/v1/jobs/walk-in", json=bad, headers=_auth(token))
        assert resp.status_code == 422, bad


def test_contractor_can_advance_a_walk_in_job(client):
    token = _register_and_login(client, "wi-contractor5@example.com", "contractor")
    job = client.post("/v1/jobs/walk-in", json=WALK_IN, headers=_auth(token)).json()
    resp = client.patch(
        f"/v1/jobs/{job['job_id']}/status", json={"status": "site_location"}, headers=_auth(token)
    )
    assert resp.status_code == 200
    assert resp.json()["walk_in"] is True
