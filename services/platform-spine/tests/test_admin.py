"""Admin adds contractors; admin lists accounts; email handling; and that a
resource_owner can no longer read customers' jobs."""
import pytest
from app import models
from app.bootstrap import ensure_admin
from app.security import hash_password

PASSWORD = "pass12345678"


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client, email, password=PASSWORD):
    resp = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _register(client, email, role):
    resp = client.post(
        "/v1/auth/register", json={"email": email, "password": PASSWORD, "role": role}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def admin(client):
    db = client.test_session_local()
    try:
        assert ensure_admin(db, "root@borewell.example.com", PASSWORD)
    finally:
        db.close()
    return _login(client, "root@borewell.example.com")


def _add(client, admin, **overrides):
    body = {"email": "new.contractor@example.com", "password": PASSWORD, "phone": "9876543210"}
    body.update(overrides)
    return client.post("/v1/admin/contractors", json=body, headers=_h(admin))


# ---------- adding a contractor ----------
def test_admin_can_add_a_contractor_who_can_then_sign_in(client, admin):
    resp = _add(client, admin)

    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "contractor" and body["email"] == "new.contractor@example.com"
    assert "password" not in body and "password_hash" not in body
    token = _login(client, "new.contractor@example.com")
    assert client.get("/v1/jobs", headers=_h(token)).status_code == 200


def test_adding_a_contractor_works_when_public_contractor_signup_is_closed(
    client, admin, monkeypatch
):
    monkeypatch.setenv("ALLOW_PUBLIC_CONTRACTOR_REGISTRATION", "0")
    public = client.post(
        "/v1/auth/register",
        json={"email": "walkup@example.com", "password": PASSWORD, "role": "contractor"},
    )
    assert public.status_code == 403
    assert _add(client, admin).status_code == 201


@pytest.mark.parametrize("role", ["customer", "contractor", "resource_owner"])
def test_only_an_admin_can_add_contractors(client, role):
    token = _register(client, f"{role}@example.com", role)
    assert _add(client, token).status_code == 403


def test_adding_a_contractor_requires_a_login(client):
    resp = client.post(
        "/v1/admin/contractors", json={"email": "a@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 401


def test_the_admin_endpoint_cannot_be_used_to_create_other_roles(client, admin):
    resp = _add(client, admin, role="admin")
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "email",
    [
        "not-an-email",
        "a@b",
        "two@@example.com",
        "spaces in@example.com",
        "no-domain@",
        "@x.com",
        "",
    ],
)
def test_invalid_emails_are_rejected(client, admin, email):
    assert _add(client, admin, email=email).status_code == 422
    reg = client.post("/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert reg.status_code == 422


def test_weak_password_and_bad_phone_are_rejected(client, admin):
    assert _add(client, admin, password="short").status_code == 422
    assert _add(client, admin, phone="12345").status_code == 422


def test_duplicate_email_is_refused_whatever_the_case(client, admin):
    assert _add(client, admin, email="Same.Person@Example.com").status_code == 201
    again = _add(client, admin, email="same.person@example.com")
    assert again.status_code == 409 and again.json()["error"]["code"] == "EMAIL_TAKEN"
    reg = client.post(
        "/v1/auth/register", json={"email": "SAME.PERSON@example.com", "password": PASSWORD}
    )
    assert reg.status_code == 409


# ---------- email case ----------
def test_email_is_stored_lower_case_and_login_ignores_case(client):
    _register(client, "Mixed.Case@Example.com", "customer")
    db = client.test_session_local()
    try:
        assert db.query(models.User).one().email == "mixed.case@example.com"
    finally:
        db.close()
    assert _login(client, "MIXED.CASE@example.COM")


def test_an_account_stored_with_capitals_before_this_change_can_still_sign_in(client):
    db = client.test_session_local()
    try:
        db.add(
            models.User(
                email="Legacy.User@Example.com",
                password_hash=hash_password(PASSWORD),
                role="customer",
            )
        )
        db.commit()
    finally:
        db.close()
    assert _login(client, "legacy.user@example.com")


# ---------- listing accounts ----------
def test_admin_lists_accounts_with_an_optional_role_filter(client, admin):
    _register(client, "cust@example.com", "customer")
    _add(client, admin)

    everyone = client.get("/v1/admin/users", headers=_h(admin)).json()
    assert {u["role"] for u in everyone} == {"admin", "customer", "contractor"}
    assert all("password" not in u and "password_hash" not in u for u in everyone)

    contractors = client.get("/v1/admin/users?role=contractor", headers=_h(admin)).json()
    assert [u["email"] for u in contractors] == ["new.contractor@example.com"]
    assert client.get("/v1/admin/users?role=wizard", headers=_h(admin)).status_code == 422


@pytest.mark.parametrize("role", ["customer", "contractor", "resource_owner"])
def test_only_an_admin_can_list_accounts(client, role):
    token = _register(client, f"{role}-list@example.com", role)
    assert client.get("/v1/admin/users", headers=_h(token)).status_code == 403


# ---------- a rig owner must not read customers' jobs ----------
def test_resource_owner_cannot_read_jobs(client):
    customer = _register(client, "job.owner@example.com", "customer")
    owner = _register(client, "rig.owner@example.com", "resource_owner")
    job = client.post(
        "/v1/jobs",
        json={"location": {"lat": 9.9, "lng": 78.1}, "job_type": "residential"},
        headers=_h(customer),
    ).json()

    assert client.get("/v1/jobs", headers=_h(owner)).status_code == 403
    assert client.get(f"/v1/jobs/{job['job_id']}", headers=_h(owner)).status_code == 403
    assert (
        client.get(f"/v1/jobs/{job['job_id']}/completion/result", headers=_h(owner)).status_code
        == 403
    )
    assert client.get(f"/v1/jobs/{job['job_id']}", headers=_h(customer)).status_code == 200
