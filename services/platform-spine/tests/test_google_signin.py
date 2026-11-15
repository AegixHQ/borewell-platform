"""Google sign-in. The ID token is a real RS256 JWT signed with a key the test
generates; only the step that downloads Google's public keys is replaced."""

import time

import jwt
import pytest
from app import google_auth
from cryptography.hazmat.primitives.asymmetric import rsa

CLIENT_ID = "123-web.apps.googleusercontent.com"
ANDROID_ID = "123-android.apps.googleusercontent.com"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def google_on(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_IDS", f"{CLIENT_ID}, {ANDROID_ID}")
    monkeypatch.setattr(google_auth, "_signing_key", lambda token: _KEY.public_key())


def id_token(email="asha@gmail.com", sub="g-1", aud=CLIENT_ID, key=_KEY, **over):
    claims = {
        "iss": "https://accounts.google.com",
        "aud": aud,
        "sub": sub,
        "email": email,
        "email_verified": True,
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
    }
    claims.update(over)
    return jwt.encode(claims, key, algorithm="RS256")


def sign_in(client, token, role=None):
    body = {"id_token": token}
    if role:
        body["role"] = role
    return client.post("/v1/auth/google", json=body)


def test_new_google_user_with_a_role_gets_an_account_and_token(client):
    resp = sign_in(client, id_token(), role="customer")
    assert resp.status_code == 200
    assert resp.json()["role"] == "customer" and resp.json()["new_account"] is True
    me = client.get("/v1/jobs", headers={"Authorization": f"Bearer {resp.json()['access_token']}"})
    assert me.status_code == 200


def test_returning_google_user_signs_in_without_a_role(client):
    sign_in(client, id_token(), role="resource_owner")
    again = sign_in(client, id_token())
    assert again.status_code == 200
    assert again.json()["role"] == "resource_owner" and again.json()["new_account"] is False


def test_unknown_google_user_without_a_role_is_asked_for_one(client):
    resp = sign_in(client, id_token())
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "ROLE_REQUIRED"


def test_android_client_id_is_accepted_too(client):
    assert sign_in(client, id_token(aud=ANDROID_ID), role="customer").status_code == 200


def test_token_for_someone_elses_app_is_rejected(client):
    stranger = id_token(aud="999-other-app.apps.googleusercontent.com")
    resp = sign_in(client, stranger, role="customer")
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "INVALID_GOOGLE_TOKEN"


def test_token_signed_with_the_wrong_key_is_rejected(client):
    assert sign_in(client, id_token(key=_OTHER_KEY), role="customer").status_code == 401


def test_expired_token_is_rejected(client):
    past = int(time.time()) - 3600
    assert sign_in(client, id_token(exp=past), role="customer").status_code == 401


def test_wrong_issuer_is_rejected(client):
    forged = id_token(iss="https://evil.example")
    assert sign_in(client, forged, role="customer").status_code == 401


def test_unverified_google_email_is_rejected(client):
    assert sign_in(client, id_token(email_verified=False), role="customer").status_code == 401


def test_unsigned_token_is_rejected(client):
    claims = {"aud": CLIENT_ID, "sub": "x", "email": "a@b.com"}
    forged = jwt.encode(claims, None, algorithm="none") + "padding-to-reach-min-length"
    assert sign_in(client, forged, role="customer").status_code == 401


def test_off_when_no_client_ids_configured(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_IDS")
    resp = sign_in(client, id_token(), role="customer")
    assert resp.status_code == 503 and resp.json()["error"]["code"] == "GOOGLE_NOT_CONFIGURED"


def test_google_cannot_create_an_admin(client):
    resp = client.post("/v1/auth/google", json={"id_token": id_token(), "role": "admin"})
    assert resp.status_code == 422


def test_contractor_signup_via_google_respects_the_closed_flag(client, monkeypatch):
    monkeypatch.setenv("ALLOW_PUBLIC_CONTRACTOR_REGISTRATION", "0")
    resp = sign_in(client, id_token(), role="contractor")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CONTRACTOR_REGISTRATION_CLOSED"


def test_admin_account_cannot_sign_in_with_google(client):
    from app.bootstrap import ensure_user

    with client.test_session_local() as db:
        ensure_user(db, "boss@example.com", "a-long-password-123", "admin")
    resp = sign_in(client, id_token(email="boss@example.com", sub="g-boss"))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ADMIN_GOOGLE_SIGNIN_DISABLED"


def test_linking_to_a_password_account_retires_that_password(client):
    """Registration does not verify the email, so a password set by whoever
    registered first must stop working once the real owner signs in with Google."""
    client.post(
        "/v1/auth/register",
        json={"email": "asha@gmail.com", "password": "squatter-password-1", "role": "customer"},
    )
    assert sign_in(client, id_token()).status_code == 200  # links to the existing customer
    login = client.post(
        "/v1/auth/login", json={"email": "asha@gmail.com", "password": "squatter-password-1"}
    )
    assert login.status_code == 401


def test_same_email_with_a_different_google_account_is_refused(client):
    sign_in(client, id_token(sub="g-1"), role="customer")
    resp = sign_in(client, id_token(sub="g-2"))
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "GOOGLE_ACCOUNT_MISMATCH"


def test_google_only_account_cannot_be_password_logged_into(client):
    sign_in(client, id_token(), role="customer")
    creds = {"email": "asha@gmail.com", "password": "anything-at-all"}
    login = client.post("/v1/auth/login", json=creds)
    assert login.status_code == 401


def test_key_download_failure_is_a_502_not_a_login(client, monkeypatch):
    def boom(token):
        raise jwt.PyJWKClientConnectionError("offline")

    monkeypatch.setattr(google_auth, "_signing_key", boom)
    resp = sign_in(client, id_token(), role="customer")
    assert resp.status_code == 502 and resp.json()["error"]["code"] == "GOOGLE_UNAVAILABLE"
