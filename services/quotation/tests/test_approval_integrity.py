"""A customer may only decide on the LATEST version of a quotation, and a
decision is a one-way state machine. Before this, approve/reject just
overwrote `status` on whatever row the ID pointed at - so an old, cheaper
version could be approved (and then paid) after the contractor revised the
price, and an approved quotation could be flipped to rejected after payment."""

from tests.conftest import make_token, user_uuid
from tests.test_quotations import _quote_request, _setup_rule


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _v1(client_factory, label):
    c = client_factory(customer_id=user_uuid(f"cust-{label}"))
    contractor = _setup_rule(c, f"contractor-{label}")
    quote = c.post("/v1/quotations", json=_quote_request(), headers=_auth(contractor)).json()
    return c, contractor, make_token(f"cust-{label}", "customer"), quote


def _revise(c, contractor, quotation_id, total="99999"):
    resp = c.patch(
        f"/v1/quotations/{quotation_id}",
        json={"total_estimate": total},
        headers=_auth(contractor),
    )
    assert resp.status_code == 201
    return resp.json()


def test_superseded_version_cannot_be_approved(client_factory):
    c, contractor, cust, v1 = _v1(client_factory, "sup-appr")
    v2 = _revise(c, contractor, v1["quotation_id"])
    assert v2["version"] == 2

    resp = c.post(f"/v1/quotations/{v1['quotation_id']}/approve", headers=_auth(cust))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "QUOTATION_SUPERSEDED"
    # and the latest version is still the one waiting for a decision
    latest = c.get(f"/v1/quotations/job/{v1['job_id']}/latest", headers=_auth(cust)).json()
    assert (latest["version"], latest["status"]) == (2, "draft")


def test_superseded_version_cannot_be_rejected(client_factory):
    c, contractor, cust, v1 = _v1(client_factory, "sup-rej")
    _revise(c, contractor, v1["quotation_id"])
    resp = c.post(f"/v1/quotations/{v1['quotation_id']}/reject", headers=_auth(cust))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "QUOTATION_SUPERSEDED"


def test_an_approved_version_reads_as_superseded_once_revised(client_factory):
    """BR-06: editing after approval requires re-approval, so the old
    approval must stop counting - payments only accepts status == approved."""
    c, contractor, cust, v1 = _v1(client_factory, "revise-after-approve")
    assert (
        c.post(f"/v1/quotations/{v1['quotation_id']}/approve", headers=_auth(cust)).status_code
        == 200
    )
    assert (
        c.get(f"/v1/quotations/{v1['quotation_id']}", headers=_auth(cust)).json()["status"]
        == "approved"
    )

    _revise(c, contractor, v1["quotation_id"])
    assert (
        c.get(f"/v1/quotations/{v1['quotation_id']}", headers=_auth(cust)).json()["status"]
        == "superseded"
    )


def test_approved_quotation_cannot_be_rejected(client_factory):
    c, _, cust, v1 = _v1(client_factory, "appr-then-rej")
    assert (
        c.post(f"/v1/quotations/{v1['quotation_id']}/approve", headers=_auth(cust)).status_code
        == 200
    )
    resp = c.post(f"/v1/quotations/{v1['quotation_id']}/reject", headers=_auth(cust))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "QUOTATION_STATE_CONFLICT"
    assert (
        c.get(f"/v1/quotations/{v1['quotation_id']}", headers=_auth(cust)).json()["status"]
        == "approved"
    )


def test_rejected_quotation_cannot_be_approved(client_factory):
    c, _, cust, v1 = _v1(client_factory, "rej-then-appr")
    assert (
        c.post(f"/v1/quotations/{v1['quotation_id']}/reject", headers=_auth(cust)).status_code
        == 200
    )
    resp = c.post(f"/v1/quotations/{v1['quotation_id']}/approve", headers=_auth(cust))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "QUOTATION_STATE_CONFLICT"


def test_repeating_the_same_decision_is_idempotent(client_factory):
    c, _, cust, v1 = _v1(client_factory, "idem")
    first = c.post(f"/v1/quotations/{v1['quotation_id']}/approve", headers=_auth(cust))
    again = c.post(f"/v1/quotations/{v1['quotation_id']}/approve", headers=_auth(cust))
    assert (first.status_code, again.status_code) == (200, 200)
    assert again.json()["status"] == "approved"
