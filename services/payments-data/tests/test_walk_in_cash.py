"""Recording a walk-in customer's cash (no account, no app). Allowed ONLY for a
walk-in quotation, by the contractor who quoted it - never as a shortcut to
mark an app customer's job paid."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from tests.conftest import DEFAULT_JOB_ID, make_token

CONTRACTOR_LABEL = "contractor-1"
CONTRACTOR = make_token(CONTRACTOR_LABEL, "contractor")
ADMIN = make_token("admin-1", "admin")
CUSTOMER = make_token("cust-1", "customer")
OWNER = make_token("owner-1", "resource_owner")
WALK_IN_CUSTOMER_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "walk-in-customer"))


def _contractor_id(label=CONTRACTOR_LABEL):
    from tests.conftest import _NAMESPACE

    return str(uuid.uuid5(_NAMESPACE, label))


def _fetcher(
    walk_in=True, status="approved", total=Decimal("95450.00"), contractor_label=CONTRACTOR_LABEL
):
    def _fetch(quotation_id, auth_header):
        return {
            "quotation_id": quotation_id,
            "job_id": DEFAULT_JOB_ID,
            "status": status,
            "total_estimate": total,
            "customer_id": WALK_IN_CUSTOMER_ID,
            "contractor_id": _contractor_id(contractor_label),
            "walk_in": walk_in,
        }

    return lambda: _fetch


def _payload(**overrides):
    p = {
        "job_id": DEFAULT_JOB_ID,
        "quotation_id": str(uuid.uuid4()),
        "amount": "95450.00",
        "idempotency_key": str(uuid.uuid4()),
    }
    p.update(overrides)
    return p


def _post(c, token, payload):
    return c.post(
        "/v1/payments/walk-in-cash", json=payload, headers={"Authorization": f"Bearer {token}"}
    )


def test_contractor_records_walk_in_cash_as_completed(client_factory):
    c = client_factory(fetcher=_fetcher())
    with patch("app.main.events.payment_completed") as fired:
        resp = _post(c, CONTRACTOR, _payload())
    assert resp.status_code == 201
    body = resp.json()
    assert (body["status"], body["method"]) == ("completed", "cash")
    assert Decimal(body["amount"]) == Decimal("95450.00")
    assert body["cash_confirmed_at"] is not None
    fired.assert_called_once()  # the job moves on exactly as for any completed payment
    assert fired.call_args.kwargs["job_id"] == DEFAULT_JOB_ID


def test_payment_is_recorded_against_the_walk_in_customer_not_the_contractor(client_factory):
    c = client_factory(fetcher=_fetcher())
    pid = _post(c, CONTRACTOR, _payload()).json()["payment_id"]
    listed = c.get("/v1/payments", headers={"Authorization": f"Bearer {CONTRACTOR}"}).json()
    assert [p["payment_id"] for p in listed] == [pid]
    # an app customer sees nothing of it
    assert c.get("/v1/payments", headers={"Authorization": f"Bearer {CUSTOMER}"}).json() == []
    other = c.get(f"/v1/payments/{pid}", headers={"Authorization": f"Bearer {CUSTOMER}"})
    assert other.status_code == 403


def test_admin_can_record_walk_in_cash(client_factory):
    c = client_factory(fetcher=_fetcher())
    assert _post(c, ADMIN, _payload()).status_code == 201


def test_it_is_refused_for_an_app_customers_quotation(client_factory):
    c = client_factory(fetcher=_fetcher(walk_in=False))
    with patch("app.main.events.payment_completed") as fired:
        resp = _post(c, CONTRACTOR, _payload())
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_A_WALK_IN"
    fired.assert_not_called()
    assert c.get("/v1/payments", headers={"Authorization": f"Bearer {CONTRACTOR}"}).json() == []


def test_only_contractor_or_admin_may_use_it(client_factory):
    c = client_factory(fetcher=_fetcher())
    assert _post(c, CUSTOMER, _payload()).status_code == 403
    assert _post(c, OWNER, _payload()).status_code == 403
    assert c.post("/v1/payments/walk-in-cash", json=_payload()).status_code == 401


def test_a_different_contractor_cannot_record_it(client_factory):
    c = client_factory(fetcher=_fetcher(contractor_label="the-real-contractor"))
    resp = _post(c, CONTRACTOR, _payload())
    assert resp.status_code == 403


def test_quotation_must_be_approved(client_factory):
    for status in ("draft", "rejected", "superseded"):
        c = client_factory(fetcher=_fetcher(status=status))
        resp = _post(c, CONTRACTOR, _payload())
        assert resp.status_code == 400, status
        assert resp.json()["error"]["code"] == "QUOTATION_NOT_APPROVED"


def test_amount_must_match_the_total_exactly(client_factory):
    c = client_factory(fetcher=_fetcher())
    for amount in ("95449.99", "100000", "1"):
        resp = _post(c, CONTRACTOR, _payload(amount=amount))
        assert resp.status_code == 400, amount
        assert resp.json()["error"]["code"] == "AMOUNT_MISMATCH"


def test_job_must_match_the_quotation(client_factory):
    c = client_factory(fetcher=_fetcher())
    resp = _post(c, CONTRACTOR, _payload(job_id=str(uuid.uuid4())))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "JOB_QUOTATION_MISMATCH"


def test_it_cannot_be_recorded_twice_for_one_quotation(client_factory):
    c = client_factory(fetcher=_fetcher())
    q = str(uuid.uuid4())
    assert _post(c, CONTRACTOR, _payload(quotation_id=q)).status_code == 201
    with patch("app.main.events.payment_completed") as fired:
        again = _post(c, CONTRACTOR, _payload(quotation_id=q))  # fresh idempotency key
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ALREADY_PAID"
    fired.assert_not_called()


def test_replaying_the_same_idempotency_key_returns_the_same_payment(client_factory):
    c = client_factory(fetcher=_fetcher())
    payload = _payload()
    first = _post(c, CONTRACTOR, payload)
    with patch("app.main.events.payment_completed") as fired:
        second = _post(c, CONTRACTOR, payload)
    assert second.status_code == 201
    assert second.json()["payment_id"] == first.json()["payment_id"]
    fired.assert_not_called()  # the event fired once, on the first call only


def test_idempotency_key_cannot_be_reused_for_a_different_request(client_factory):
    c = client_factory(fetcher=_fetcher())
    payload = _payload()
    assert _post(c, CONTRACTOR, payload).status_code == 201
    other = _payload(idempotency_key=payload["idempotency_key"])
    resp = _post(c, CONTRACTOR, other)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    # nor can another contractor read the first one's payment through the key
    stranger = make_token("contractor-9", "contractor")
    assert _post(c, stranger, payload).status_code == 409


def test_quotation_service_errors_surface_cleanly(client_factory):
    from tests.conftest import access_denied_fetcher, not_found_fetcher

    c = client_factory(fetcher=lambda: not_found_fetcher())
    assert _post(c, CONTRACTOR, _payload()).status_code == 404
    c = client_factory(fetcher=lambda: access_denied_fetcher())
    assert _post(c, CONTRACTOR, _payload()).status_code == 403


def test_a_quotation_without_a_customer_is_refused(client_factory):
    def no_customer(quotation_id, auth_header):
        return {
            "quotation_id": quotation_id, "job_id": DEFAULT_JOB_ID, "status": "approved",
            "total_estimate": Decimal("95450.00"), "walk_in": True,
            "contractor_id": _contractor_id(),
        }

    c = client_factory(fetcher=lambda: no_customer)
    assert _post(c, CONTRACTOR, _payload()).status_code == 502


def test_existing_payment_flow_is_unchanged(client_factory):
    """create_payment now shares its checks with this endpoint; an app customer
    still creates a pending payment for their own approved quotation."""
    c = client_factory()
    resp = c.post(
        "/v1/payments",
        json=_payload(amount=95450.0),
        headers={"Authorization": f"Bearer {CUSTOMER}"},
    )
    assert resp.status_code == 201 and resp.json()["status"] == "pending"
