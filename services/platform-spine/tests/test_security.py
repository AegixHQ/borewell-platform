"""Self-registration cannot mint admins, the admin bootstrap is create-only,
and the auth endpoints are rate limited."""

import pytest
from app import models
from app.bootstrap import ensure_admin
from app.ratelimit import limiter, parse_limit

REG = {"email": "x@example.com", "password": "supersecret123"}


# ---------- admin self-registration ----------
def test_public_registration_cannot_create_admin(client):
    resp = client.post("/v1/auth/register", json={**REG, "role": "admin"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    # and no account was created as a side effect
    assert (
        client.post("/v1/auth/login", json={k: REG[k] for k in ("email", "password")}).status_code
        == 401
    )


@pytest.mark.parametrize("role", ["customer", "contractor", "resource_owner"])
def test_public_registration_still_allows_non_admin_roles(client, role):
    resp = client.post("/v1/auth/register", json={**REG, "role": role})
    assert resp.status_code == 201
    assert resp.json()["role"] == role


# ---------- admin bootstrap ----------
def test_bootstrap_creates_admin_who_can_log_in(client):
    with client.test_session_local() as db:
        assert ensure_admin(db, "root@example.com", "a-long-admin-password") is True
    resp = client.post(
        "/v1/auth/login", json={"email": "root@example.com", "password": "a-long-admin-password"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_bootstrap_is_idempotent_and_never_resets_a_password(client):
    with client.test_session_local() as db:
        assert ensure_admin(db, "root@example.com", "first-password-123") is True
        assert ensure_admin(db, "root@example.com", "different-password-456") is False
    ok = client.post(
        "/v1/auth/login", json={"email": "root@example.com", "password": "first-password-123"}
    )
    assert ok.status_code == 200


def test_bootstrap_never_promotes_an_existing_non_admin(client):
    client.post("/v1/auth/register", json={**REG, "role": "customer"})
    with client.test_session_local() as db:
        assert ensure_admin(db, REG["email"], "a-long-admin-password") is False
        assert db.query(models.User).filter_by(email=REG["email"]).one().role == "customer"


def test_bootstrap_rejects_a_short_password(client):
    with client.test_session_local() as db, pytest.raises(ValueError):
        ensure_admin(db, "root@example.com", "short")


# ---------- rate limiting ----------
@pytest.fixture()
def limiter_on(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN", "3/minute")
    monkeypatch.setenv("RATE_LIMIT_REGISTER", "2/hour")
    limiter.reset()
    yield
    limiter.reset()


def test_login_is_rate_limited_per_ip(client, limiter_on):
    bad = {"email": "nobody@example.com", "password": "wrongpassword"}
    assert [client.post("/v1/auth/login", json=bad).status_code for _ in range(3)] == [
        401,
        401,
        401,
    ]
    blocked = client.post("/v1/auth/login", json=bad)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert int(blocked.headers["Retry-After"]) >= 1


def test_login_limit_counts_malformed_requests_too(client, limiter_on):
    for _ in range(3):
        assert client.post("/v1/auth/login", json={"email": "not-an-email"}).status_code == 422
    assert client.post("/v1/auth/login", json={"email": "not-an-email"}).status_code == 429


def test_register_is_rate_limited_per_ip(client, limiter_on):
    codes = [
        client.post("/v1/auth/register", json={**REG, "email": f"u{i}@example.com"}).status_code
        for i in range(3)
    ]
    assert codes == [201, 201, 429]


def test_forwarded_for_ignored_unless_trusted(client, limiter_on):
    bad = {"email": "nobody@example.com", "password": "wrongpassword"}
    for i in range(3):
        client.post("/v1/auth/login", json=bad, headers={"X-Forwarded-For": f"9.9.9.{i}"})
    # untrusted header must NOT let a caller dodge the limit by rotating it
    assert (
        client.post("/v1/auth/login", json=bad, headers={"X-Forwarded-For": "9.9.9.99"}).status_code
        == 429
    )


def test_forwarded_for_keys_per_client_when_trusted_behind_the_gateway(
    client, limiter_on, monkeypatch
):
    monkeypatch.setenv("RATE_LIMIT_TRUST_FORWARDED_FOR", "1")
    bad = {"email": "nobody@example.com", "password": "wrongpassword"}
    for _ in range(3):
        client.post("/v1/auth/login", json=bad, headers={"X-Forwarded-For": "1.1.1.1"})
    assert (
        client.post("/v1/auth/login", json=bad, headers={"X-Forwarded-For": "1.1.1.1"}).status_code
        == 429
    )
    # a different real client behind the same gateway is unaffected
    assert (
        client.post("/v1/auth/login", json=bad, headers={"X-Forwarded-For": "2.2.2.2"}).status_code
        == 401
    )
    # only the LAST hop counts: a client-forged prefix cannot rotate the key
    forged = {"X-Forwarded-For": "6.6.6.6, 1.1.1.1"}
    assert client.post("/v1/auth/login", json=bad, headers=forged).status_code == 429


def test_parse_limit():
    assert parse_limit("10/minute") == (10, 60)
    assert parse_limit("5/hours") == (5, 3600)
    for bad in ("", "10", "ten/minute", "0/minute", "10/fortnight"):
        with pytest.raises(ValueError):
            parse_limit(bad)
