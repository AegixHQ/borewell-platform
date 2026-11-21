"""A contractor sees and settles only the payments of jobs they quoted.

Before this, GET /v1/payments returned every customer's payments to any
contractor, and any contractor could confirm or reject any customer's cash.
"""

import uuid

from app import models
from app.database import get_db
from app.main import app

from tests.conftest import contractor_uuid, make_token
from tests.test_payments import CUST_TOKEN, _payment_payload

OWNER_OF_JOB = make_token("contractor-1", "contractor")  # the fake quotation's contractor
STRANGER = make_token("contractor-9", "contractor")
ADMIN = make_token("admin-1", "admin")
RIG_OWNER = make_token("owner-1", "resource_owner")


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _cash_payment(client):
    payload = _payment_payload(quotation_id=str(uuid.uuid4()))
    resp = client.post("/v1/payments", json=payload, headers=_h(CUST_TOKEN))
    assert resp.status_code == 201
    pid = resp.json()["payment_id"]
    assert client.post(f"/v1/payments/{pid}/choose-cash", headers=_h(CUST_TOKEN)).status_code == 200
    return pid


def _status(client, pid):
    return client.get(f"/v1/payments/{pid}", headers=_h(CUST_TOKEN)).json()["status"]


def test_a_payment_remembers_the_quoting_contractor(client):
    pid = _cash_payment(client)
    db = next(app.dependency_overrides[get_db]())
    row = db.query(models.Payment).filter(models.Payment.id == pid).one()
    assert row.contractor_id == contractor_uuid("contractor-1")
    db.close()


def test_a_contractor_lists_only_their_own_payments(client):
    _cash_payment(client)
    mine = client.get("/v1/payments", headers=_h(OWNER_OF_JOB))
    theirs = client.get("/v1/payments", headers=_h(STRANGER))
    assert len(mine.json()) == 1
    assert theirs.status_code == 200 and theirs.json() == []


def test_admin_still_lists_everything(client):
    _cash_payment(client)
    assert len(client.get("/v1/payments", headers=_h(ADMIN)).json()) == 1


def test_another_contractor_cannot_confirm_the_cash(client):
    pid = _cash_payment(client)
    resp = client.post(f"/v1/payments/{pid}/confirm-cash", headers=_h(STRANGER))
    assert resp.status_code == 403
    assert _status(client, pid) == "pending"  # the job was not marked paid


def test_another_contractor_cannot_reject_the_cash(client):
    pid = _cash_payment(client)
    resp = client.post(f"/v1/payments/{pid}/reject-cash", headers=_h(STRANGER))
    assert resp.status_code == 403
    assert _status(client, pid) == "pending"


def test_the_quoting_contractor_and_an_admin_can_still_confirm(client):
    first = _cash_payment(client)
    second = _cash_payment(client)
    by_contractor = client.post(f"/v1/payments/{first}/confirm-cash", headers=_h(OWNER_OF_JOB))
    by_admin = client.post(f"/v1/payments/{second}/confirm-cash", headers=_h(ADMIN))
    assert by_contractor.status_code == 200 and by_admin.status_code == 200


def test_another_contractor_cannot_read_the_payment_by_id(client):
    pid = _cash_payment(client)
    assert client.get(f"/v1/payments/{pid}", headers=_h(STRANGER)).status_code == 403
    assert client.get(f"/v1/payments/{pid}", headers=_h(OWNER_OF_JOB)).status_code == 200


def test_a_rig_owner_cannot_read_a_payment_by_id(client):
    pid = _cash_payment(client)
    assert client.get(f"/v1/payments/{pid}", headers=_h(RIG_OWNER)).status_code == 403


def _forget_contractor(client, pid):
    """Make the row look like one created before contractor_id existed."""
    db = next(app.dependency_overrides[get_db]())
    db.query(models.Payment).filter(models.Payment.id == pid).update({"contractor_id": None})
    db.commit()
    db.close()


def test_an_old_row_is_resolved_through_the_quotation_and_remembered(client):
    pid = _cash_payment(client)
    _forget_contractor(client, pid)
    assert client.get("/v1/payments", headers=_h(OWNER_OF_JOB)).json() == []  # not listed...
    confirmed = client.post(f"/v1/payments/{pid}/confirm-cash", headers=_h(OWNER_OF_JOB))
    assert confirmed.status_code == 200
    db = next(app.dependency_overrides[get_db]())
    row = db.query(models.Payment).filter(models.Payment.id == pid).one()
    assert row.contractor_id == contractor_uuid("contractor-1")  # ...until first used
    db.close()


def test_an_old_row_is_not_open_to_a_stranger(client):
    pid = _cash_payment(client)
    _forget_contractor(client, pid)
    assert client.post(f"/v1/payments/{pid}/confirm-cash", headers=_h(STRANGER)).status_code == 403
    assert _status(client, pid) == "pending"
