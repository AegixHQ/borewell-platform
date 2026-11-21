"""Freeing a rig once its job is done: manually (contractor or owner), by the
owner setting it available, and automatically on job.completed."""
import uuid

from app.job_consumer import handle_job_completed

from tests.conftest import make_token

OWNER = make_token("rel-owner", "resource_owner")
OTHER_OWNER = make_token("rel-owner-2", "resource_owner")
CONTRACTOR = make_token("rel-contractor", "contractor")
OTHER_CONTRACTOR = make_token("rel-contractor-2", "contractor")
JOB_ID = str(uuid.uuid4())


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _accepted_booking(client, job_id=JOB_ID):
    rig = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rig", "lat": 9.9, "lng": 78.1},
        headers=_h(OWNER),
    ).json()
    booking = client.post(
        "/v1/bookings",
        json={"resource_id": rig["resource_id"], "job_id": job_id},
        headers=_h(CONTRACTOR),
    ).json()
    accepted = client.post(f"/v1/bookings/{booking['booking_id']}/accept", headers=_h(OWNER))
    assert accepted.status_code == 200
    return rig["resource_id"], booking["booking_id"]


def _rig_status(client, rig_id):
    return client.get(f"/v1/resources/{rig_id}", headers=_h(OWNER)).json()["status"]


def test_contractor_can_release_an_accepted_booking(client):
    rig_id, booking_id = _accepted_booking(client)
    assert _rig_status(client, rig_id) == "reserved"

    resp = client.post(f"/v1/bookings/{booking_id}/release", headers=_h(CONTRACTOR))

    assert resp.status_code == 200 and resp.json()["status"] == "completed"
    assert _rig_status(client, rig_id) == "available"


def test_owner_can_release_an_accepted_booking(client):
    rig_id, booking_id = _accepted_booking(client)
    resp = client.post(f"/v1/bookings/{booking_id}/release", headers=_h(OWNER))
    assert resp.status_code == 200
    assert _rig_status(client, rig_id) == "available"


def test_a_freed_rig_can_be_booked_again(client):
    rig_id, booking_id = _accepted_booking(client)
    client.post(f"/v1/bookings/{booking_id}/release", headers=_h(CONTRACTOR))

    again = client.post(
        "/v1/bookings", json={"resource_id": rig_id}, headers=_h(OTHER_CONTRACTOR)
    )
    assert again.status_code == 201


def test_release_twice_is_harmless(client):
    _, booking_id = _accepted_booking(client)
    client.post(f"/v1/bookings/{booking_id}/release", headers=_h(CONTRACTOR))
    again = client.post(f"/v1/bookings/{booking_id}/release", headers=_h(CONTRACTOR))
    assert again.status_code == 200 and again.json()["status"] == "completed"


def test_someone_elses_booking_cannot_be_released(client):
    _, booking_id = _accepted_booking(client)
    assert (
        client.post(f"/v1/bookings/{booking_id}/release", headers=_h(OTHER_CONTRACTOR)).status_code
        == 403
    )
    assert (
        client.post(f"/v1/bookings/{booking_id}/release", headers=_h(OTHER_OWNER)).status_code
        == 403
    )


def test_customer_cannot_release(client):
    _, booking_id = _accepted_booking(client)
    resp = client.post(
        f"/v1/bookings/{booking_id}/release", headers=_h(make_token("rel-cust", "customer"))
    )
    assert resp.status_code == 403


def test_pending_booking_cannot_be_released(client):
    rig = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rig", "lat": 9.9, "lng": 78.1},
        headers=_h(OWNER),
    ).json()
    booking = client.post(
        "/v1/bookings", json={"resource_id": rig["resource_id"]}, headers=_h(CONTRACTOR)
    ).json()
    resp = client.post(f"/v1/bookings/{booking['booking_id']}/release", headers=_h(CONTRACTOR))
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "BOOKING_NOT_ACTIVE"


def test_owner_setting_the_rig_available_also_ends_the_booking(client):
    # Before: the rig showed available but the accepted booking still blocked
    # every new request with RESOURCE_ALREADY_REQUESTED.
    rig_id, booking_id = _accepted_booking(client)
    client.patch(f"/v1/resources/{rig_id}", json={"status": "available"}, headers=_h(OWNER))

    bookings = client.get("/v1/bookings", headers=_h(OWNER)).json()
    assert [b["status"] for b in bookings if b["booking_id"] == booking_id] == ["completed"]
    again = client.post("/v1/bookings", json={"resource_id": rig_id}, headers=_h(OTHER_CONTRACTOR))
    assert again.status_code == 201


def test_job_completed_event_frees_the_rig_for_that_job_only(client):
    rig_a, booking_a = _accepted_booking(client, job_id=JOB_ID)
    other_job = str(uuid.uuid4())
    rig_b, _ = _accepted_booking(client, job_id=other_job)

    db = client.test_session_local()
    try:
        released = handle_job_completed({"job_id": JOB_ID}, db=db)
    finally:
        db.close()

    assert released == 1
    assert _rig_status(client, rig_a) == "available"
    assert _rig_status(client, rig_b) == "reserved"


def test_job_completed_event_is_idempotent_and_tolerates_junk(client):
    rig_id, _ = _accepted_booking(client)
    db = client.test_session_local()
    try:
        assert handle_job_completed({"job_id": JOB_ID}, db=db) == 1
        assert handle_job_completed({"job_id": JOB_ID}, db=db) == 0
        assert handle_job_completed({}, db=db) == 0
        assert handle_job_completed("nonsense", db=db) == 0
    finally:
        db.close()
    assert _rig_status(client, rig_id) == "available"
