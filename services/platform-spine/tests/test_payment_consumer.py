"""
Tests for app/payment_consumer.py's handle_payment_completed() - the real
reaction to a real event, factored out from the Redis-listening loop
specifically so it's testable like this: call it directly with a
synthetic payload against a real test-DB session, no live Redis needed.

This is the first event CONSUMER anywhere in this codebase (every prior
session's events.py files were publish-only) - these tests are the first
proof that subscribing to an event and reacting to it actually works,
not just that publishing doesn't crash.
"""
from decimal import Decimal
from unittest.mock import patch

from app.models import PaymentReceipt
from app.payment_consumer import handle_payment_completed

MOCK_QUOTATION = {
    "total_estimate": Decimal("80000.00"),
    "min_ft": 200.0,
    "max_ft": 250.0,
    "depth_overage_rate_per_ft": Decimal("150.00"),
}
MOCK_PATCH = "app.quotation_client.fetch_approved_quotation"
STAGES = [
    "site_location", "requirement", "estimation", "price_calculation",
    "quotation", "customer_approval", "booking", "resource_allocation",
    "drilling", "progress", "completion", "payment", "service_history",
]


def _register_and_login(client, email, role):
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass12345678", "role": role},
    )
    resp = client.post("/v1/auth/login", json={"email": email, "password": "pass12345678"})
    return resp.json()["access_token"]


def _create_job_at(client, cust_token, contractor_token, target="completion"):
    """Create a job and advance it, one valid step at a time, to `target`."""
    job_resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.08, "lng": 80.27}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    job_id = job_resp.json()["job_id"]
    for s in STAGES[: STAGES.index(target) + 1]:
        r = client.patch(
            f"/v1/jobs/{job_id}/status",
            json={"status": s},
            headers={"Authorization": f"Bearer {contractor_token}"},
        )
        assert r.status_code == 200, f"stage {s} failed: {r.text}"
    return job_id


def _log_completion(client, job_id, contractor_token):
    with patch(MOCK_PATCH, return_value=MOCK_QUOTATION):
        resp = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 220.0, "actual_cost": 75000.0},
            headers={"Authorization": f"Bearer {contractor_token}"},
        )
    assert resp.status_code == 201, resp.text


def _payment_event(job_id, payment_id="pay-test"):
    return {
        "payment_id": payment_id,
        "job_id": job_id,
        "amount": 95450.00,
        "completed_at": "2026-09-14T10:00:00Z",
    }


def _status(client, job_id, token):
    return client.get(f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}).json()[
        "status"
    ]


def _receipt_count(client, job_id):
    db = client.test_session_local()
    try:
        return db.query(PaymentReceipt).filter(PaymentReceipt.job_id == job_id).count()
    finally:
        db.close()


def test_payment_completed_advances_job_once_completion_record_exists(client):
    cust = _register_and_login(client, "consumer-c1@example.com", "customer")
    cont = _register_and_login(client, "consumer-k1@example.com", "contractor")
    job_id = _create_job_at(client, cust, cont)
    _log_completion(client, job_id, cont)
    assert _status(client, job_id, cont) == "completion"  # nothing paid yet

    db = client.test_session_local()
    try:
        handle_payment_completed(_payment_event(job_id, "pay-test-1"), db=db)
    finally:
        db.close()

    assert _status(client, job_id, cont) == "payment"


def test_payment_completed_does_not_advance_without_completion_record(client):
    cust = _register_and_login(client, "consumer-c6@example.com", "customer")
    cont = _register_and_login(client, "consumer-k6@example.com", "contractor")
    job_id = _create_job_at(client, cust, cont)

    db = client.test_session_local()
    try:
        handle_payment_completed(_payment_event(job_id, "pay-test-6"), db=db)
    finally:
        db.close()

    assert _status(client, job_id, cont) == "completion"
    assert _receipt_count(client, job_id) == 1  # remembered for later


def test_early_payment_is_reconciled_when_completion_is_logged(client):
    # The normal real-world order: the customer pays while the job is still
    # at 'booking', long before the contractor logs the completion record.
    cust = _register_and_login(client, "consumer-c7@example.com", "customer")
    cont = _register_and_login(client, "consumer-k7@example.com", "contractor")
    job_id = _create_job_at(client, cust, cont, target="booking")

    db = client.test_session_local()
    try:
        handle_payment_completed(_payment_event(job_id, "pay-test-7"), db=db)
    finally:
        db.close()
    assert _status(client, job_id, cont) == "booking"

    for s in STAGES[STAGES.index("booking") + 1 : STAGES.index("completion") + 1]:
        r = client.patch(
            f"/v1/jobs/{job_id}/status",
            json={"status": s},
            headers={"Authorization": f"Bearer {cont}"},
        )
        assert r.status_code == 200
    assert _status(client, job_id, cont) == "completion"  # stays until completion is logged

    _log_completion(client, job_id, cont)

    assert _status(client, job_id, cont) == "payment"


def test_completion_logged_without_payment_leaves_job_at_completion(client):
    cust = _register_and_login(client, "consumer-c8@example.com", "customer")
    cont = _register_and_login(client, "consumer-k8@example.com", "contractor")
    job_id = _create_job_at(client, cust, cont)

    _log_completion(client, job_id, cont)

    assert _status(client, job_id, cont) == "completion"


def test_failed_reconcile_does_not_fail_a_saved_completion(client):
    cust = _register_and_login(client, "consumer-c9@example.com", "customer")
    cont = _register_and_login(client, "consumer-k9@example.com", "contractor")
    job_id = _create_job_at(client, cust, cont)

    with patch(MOCK_PATCH, return_value=MOCK_QUOTATION), patch(
        "app.payment_consumer.advance_to_payment_if_ready", side_effect=RuntimeError("boom")
    ):
        resp = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 220.0, "actual_cost": 75000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )

    assert resp.status_code == 201
    get_resp = client.get(
        f"/v1/jobs/{job_id}/completion/result", headers={"Authorization": f"Bearer {cont}"}
    )
    assert get_resp.status_code == 200


def test_payment_completed_skips_job_not_at_completion_status(client):
    # A job still at 'lead' (never advanced) must not be force-advanced -
    # this event is only valid to react to from exactly 'completion'.
    cust = _register_and_login(client, "consumer-c2@example.com", "customer")
    job_resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.08, "lng": 80.27}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {cust}"},
    )
    job_id = job_resp.json()["job_id"]

    db = client.test_session_local()
    try:
        handle_payment_completed(
            {
                "payment_id": "pay-test-2",
                "job_id": job_id,
                "amount": 50000.00,
                "completed_at": "2026-09-14T10:00:00Z",
            },
            db=db,
        )
    finally:
        db.close()

    check = client.get(f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {cust}"})
    assert check.json()["status"] == "lead"


def test_payment_completed_is_idempotent_on_redelivery(client):
    # Redis pub/sub doesn't guarantee exactly-once, same as Razorpay's
    # webhooks - a redelivered event must be a no-op, not an error, and must
    # not force any further transition or create a second receipt.
    cust = _register_and_login(client, "consumer-c3@example.com", "customer")
    cont = _register_and_login(client, "consumer-k3@example.com", "contractor")
    job_id = _create_job_at(client, cust, cont)
    _log_completion(client, job_id, cont)

    event = _payment_event(job_id, "pay-test-3")
    db = client.test_session_local()
    try:
        handle_payment_completed(event, db=db)
        handle_payment_completed(event, db=db)
    finally:
        db.close()

    assert _status(client, job_id, cont) == "payment"
    assert _receipt_count(client, job_id) == 1


def test_payment_completed_unknown_job_id_does_not_raise(client):
    db = client.test_session_local()
    try:
        # Must not raise - an event for a job this service has no record
        # of should log and continue, not crash the subscriber.
        handle_payment_completed(
            {
                "payment_id": "pay-test-4",
                "job_id": "00000000-0000-0000-0000-000000000000",
                "amount": 1000.00,
                "completed_at": "2026-09-14T10:00:00Z",
            },
            db=db,
        )
    finally:
        db.close()


def test_payment_completed_missing_job_id_does_not_raise(client):
    db = client.test_session_local()
    try:
        # A malformed payload (missing required field) must be dropped,
        # not crash the caller.
        handle_payment_completed({"payment_id": "pay-test-5"}, db=db)
    finally:
        db.close()
