def test_register_creates_user_and_returns_token(client):
    resp = client.post(
        "/v1/auth/register",
        json={"email": "customer@example.com", "password": "supersecret123", "role": "customer"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "customer"
    assert body["access_token"]


def test_register_duplicate_email_rejected(client):
    payload = {"email": "dupe@example.com", "password": "supersecret123", "role": "customer"}
    first = client.post("/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = client.post("/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EMAIL_TAKEN"


def test_login_with_correct_credentials(client):
    client.post(
        "/v1/auth/register",
        json={"email": "a@example.com", "password": "supersecret123", "role": "contractor"},
    )
    login_payload = {"email": "a@example.com", "password": "supersecret123"}
    resp = client.post("/v1/auth/login", json=login_payload)
    assert resp.status_code == 200
    assert resp.json()["role"] == "contractor"


def test_login_wrong_password_rejected(client):
    client.post(
        "/v1/auth/register",
        json={"email": "b@example.com", "password": "supersecret123", "role": "customer"},
    )
    login_payload = {"email": "b@example.com", "password": "wrongpassword"}
    resp = client.post("/v1/auth/login", json=login_payload)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_protected_endpoint_without_token_rejected(client):
    resp = client.get("/v1/jobs")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MISSING_TOKEN"


def test_protected_endpoint_with_garbage_token_rejected(client):
    resp = client.get("/v1/jobs", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_TOKEN"
