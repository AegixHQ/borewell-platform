"""Idempotency keys belong to the customer and request that made them, and a
quotation can have only one live payment. Before this, a replayed key
returned whoever's payment it matched, and a fresh key could open a second
(or third) charge for the same quotation."""

import uuid

from tests.conftest import make_token
from tests.test_payments import CUST_TOKEN, _payment_payload

OTHER_TOKEN = make_token("cust-2", "customer")
ADMIN_TOKEN = make_token("admin-1", "admin")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, token=CUST_TOKEN, **overrides):
    return client.post("/v1/payments", json=_payment_payload(**overrides), headers=_auth(token))


# ---------- idempotency key ownership ----------
def test_another_customers_idempotency_key_does_not_return_their_payment(client):
    key = str(uuid.uuid4())
    mine = _create(client, idempotency_key=key)
    assert mine.status_code == 201

    stolen = _create(client, token=OTHER_TOKEN, idempotency_key=key)
    assert stolen.status_code == 409
    assert stolen.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert mine.json()["payment_id"] not in stolen.text  # nothing about their payment leaks


def test_same_key_with_a_different_request_is_a_conflict_not_a_silent_replay(client):
    key = str(uuid.uuid4())
    assert _create(client, idempotency_key=key).status_code == 201
    other_quotation = _create(client, idempotency_key=key, quotation_id=str(uuid.uuid4()))
    assert other_quotation.status_code == 409
    assert other_quotation.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_exact_replay_still_returns_the_original_payment(client):
    key, quotation = str(uuid.uuid4()), str(uuid.uuid4())
    first = _create(client, idempotency_key=key, quotation_id=quotation)
    again = _create(client, idempotency_key=key, quotation_id=quotation)
    assert again.status_code == 201
    assert again.json()["payment_id"] == first.json()["payment_id"]


def test_overlong_idempotency_key_is_rejected(client):
    assert _create(client, idempotency_key="k" * 129).status_code == 422


# ---------- one live payment per quotation ----------
def test_fresh_key_for_a_quotation_with_a_pending_payment_continues_that_payment(client):
    quotation = str(uuid.uuid4())
    first = _create(client, quotation_id=quotation)
    retry = _create(client, quotation_id=quotation)  # new idempotency key
    assert retry.status_code == 201
    assert retry.json()["payment_id"] == first.json()["payment_id"]
    listing = client.get("/v1/payments", headers=_auth(CUST_TOKEN)).json()
    assert len([p for p in listing if p["quotation_id"] == quotation]) == 1


def test_a_paid_quotation_cannot_be_paid_again_with_a_fresh_key(client):
    quotation = str(uuid.uuid4())
    payment_id = _create(client, quotation_id=quotation).json()["payment_id"]
    assert (
        client.post(f"/v1/payments/{payment_id}/confirm", headers=_auth(ADMIN_TOKEN)).status_code
        == 200
    )

    again = _create(client, quotation_id=quotation)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ALREADY_PAID"


def test_a_failed_payment_does_not_block_a_retry(client):
    quotation = str(uuid.uuid4())
    failed_id = _create(client, quotation_id=quotation).json()["payment_id"]
    assert (
        client.post(f"/v1/payments/{failed_id}/fail", headers=_auth(ADMIN_TOKEN)).status_code == 200
    )

    retry = _create(client, quotation_id=quotation)
    assert retry.status_code == 201
    assert retry.json()["payment_id"] != failed_id
    assert retry.json()["status"] == "pending"


def test_unrelated_quotations_are_not_affected(client):
    a, b = _create(client), _create(client)
    assert a.status_code == b.status_code == 201
    assert a.json()["payment_id"] != b.json()["payment_id"]
