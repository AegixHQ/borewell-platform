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
from app.payment_consumer import handle_payment_completed


def _register_and_login(client, email, role):
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass12345678", "role": role},
    )
    resp = client.post("/v1/auth/login", json={"email": email, "password": "pass12345678"})
    return resp.json()["access_token"]


def _create_job_at_completion(client, cust_token, contractor_token):
    """Same helper as test_completion.py - creates a job and advances it
    all the way to 'completion', the one status payment.completed is
    valid to advance past."""
    job_resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.08, "lng": 80.27}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    job_id = job_resp.json()["job_id"]
    stages = [
        "site_location", "requirement", "estimation", "price_calculation",
        "quotation", "customer_approval", "booking", "resource_allocation",
        "drilling", "progress", "completion",
    ]
    for s in stages:
        r = client.patch(
            f"/v1/jobs/{job_id}/status",
            json={"status": s},
            headers={"Authorization": f"Bearer {contractor_token}"},
        )
        assert r.status_code == 200, f"stage {s} failed: {r.text}"
    return job_id


def test_payment_completed_advances_job_from_completion_to_payment(client):
    cust = _register_and_login(client, "consumer-c1@example.com", "customer")
    cont = _register_and_login(client, "consumer-k1@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust, cont)

    db = client.test_session_local()
    try:
        handle_payment_completed(
            {
                "payment_id": "pay-test-1",
                "job_id": job_id,
                "amount": 95450.00,
                "completed_at": "2026-09-14T10:00:00Z",
            },
            db=db,
        )
    finally:
        db.close()

    check = client.get(f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {cont}"})
    assert check.json()["status"] == "payment"


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
    # webhooks - a redelivered event for a job already advanced past
    # 'completion' must be a no-op, not an error.
    cust = _register_and_login(client, "consumer-c3@example.com", "customer")
    cont = _register_and_login(client, "consumer-k3@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust, cont)

    event = {
        "payment_id": "pay-test-3",
        "job_id": job_id,
        "amount": 95450.00,
        "completed_at": "2026-09-14T10:00:00Z",
    }
    db = client.test_session_local()
    try:
        handle_payment_completed(event, db=db)
        # Redelivery - must not raise, must not force any further transition.
        handle_payment_completed(event, db=db)
    finally:
        db.close()

    check = client.get(f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {cont}"})
    assert check.json()["status"] == "payment"


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
