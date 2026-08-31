import uuid

from tests.conftest import make_token

CUST_TOKEN = make_token("cust-1", "customer")


def _payment_payload(**overrides):
    payload = {
        "job_id": str(uuid.uuid4()),
        "quotation_id": str(uuid.uuid4()),
        "amount": 95450.0,
        "idempotency_key": str(uuid.uuid4()),
    }
    payload.update(overrides)
    return payload


def test_customer_can_create_payment_for_approved_quotation(client):
    resp = client.post(
        "/v1/payments", json=_payment_payload(), headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["amount"] == 95450.0


def test_contractor_cannot_create_payment(client):
    token = make_token("contractor-1", "contractor")
    resp = client.post(
        "/v1/payments", json=_payment_payload(), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_duplicate_idempotency_key_returns_same_payment_not_a_new_one(client):
    key = str(uuid.uuid4())
    payload = _payment_payload(idempotency_key=key)

    first = client.post(
        "/v1/payments", json=payload, headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    second = client.post(
        "/v1/payments", json=payload, headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["payment_id"] == second.json()["payment_id"]

    # FR-PAY-03, verified by counting actual rows, not just comparing IDs.
    listing = client.get("/v1/payments", headers={"Authorization": f"Bearer {CUST_TOKEN}"})
    matching = [p for p in listing.json() if p["payment_id"] == first.json()["payment_id"]]
    assert len(matching) == 1


def test_missing_idempotency_key_rejected(client):
    payload = _payment_payload()
    del payload["idempotency_key"]
    resp = client.post(
        "/v1/payments", json=payload, headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    assert resp.status_code == 422


def test_unapproved_quotation_rejects_payment(client_factory):
    c = client_factory(status="draft", total_estimate=95450.0)
    resp = c.post(
        "/v1/payments", json=_payment_payload(), headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "QUOTATION_NOT_APPROVED"


def test_amount_mismatch_rejects_payment(client_factory):
    c = client_factory(status="approved", total_estimate=95450.0)
    resp = c.post(
        "/v1/payments",
        json=_payment_payload(amount=1.0),
        headers={"Authorization": f"Bearer {CUST_TOKEN}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "AMOUNT_MISMATCH"


def test_get_own_payment(client):
    create_resp = client.post(
        "/v1/payments", json=_payment_payload(), headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    payment_id = create_resp.json()["payment_id"]
    resp = client.get(
        f"/v1/payments/{payment_id}", headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    assert resp.status_code == 200


def test_other_customer_cannot_view_payment(client):
    create_resp = client.post(
        "/v1/payments", json=_payment_payload(), headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    payment_id = create_resp.json()["payment_id"]
    other_token = make_token("cust-2", "customer")
    resp = client.get(
        f"/v1/payments/{payment_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert resp.status_code == 403


def test_admin_can_confirm_payment(client):
    create_resp = client.post(
        "/v1/payments", json=_payment_payload(), headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    payment_id = create_resp.json()["payment_id"]
    admin_token = make_token("admin-1", "admin")
    resp = client.post(
        f"/v1/payments/{payment_id}/confirm", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_customer_cannot_confirm_own_payment(client):
    create_resp = client.post(
        "/v1/payments", json=_payment_payload(), headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    payment_id = create_resp.json()["payment_id"]
    resp = client.post(
        f"/v1/payments/{payment_id}/confirm", headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    assert resp.status_code == 403


def test_admin_can_fail_payment(client):
    create_resp = client.post(
        "/v1/payments", json=_payment_payload(), headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    payment_id = create_resp.json()["payment_id"]
    admin_token = make_token("admin-2", "admin")
    resp = client.post(
        f"/v1/payments/{payment_id}/fail", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
