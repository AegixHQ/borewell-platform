"""Walk-in customers (no account): the contractor decides for them - and ONLY
for them. A contractor must never be able to approve an app customer's quote."""

from tests.conftest import make_token, user_uuid
from tests.test_quotations import _quote_request, _setup_rule


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _fetcher(walk_in, customer_label="walk-in-customer"):
    def _fetch(job_id, auth_header):
        return {
            "job_id": job_id,
            "customer_id": user_uuid(customer_label),
            "status": "lead",
            "walk_in": walk_in,
        }

    return lambda: _fetch


def _quote(client_factory, label, walk_in=True):
    c = client_factory(job_fetcher=_fetcher(walk_in))
    contractor = _setup_rule(c, f"contractor-{label}")
    quote = c.post("/v1/quotations", json=_quote_request(), headers=_auth(contractor)).json()
    return c, contractor, quote


def test_quotation_records_that_the_job_is_a_walk_in(client_factory):
    _, _, quote = _quote(client_factory, "wi-flag")
    assert quote["walk_in"] is True
    assert quote["customer_id"] == user_uuid("walk-in-customer")
    assert quote["decided_by"] is None


def test_normal_job_quotation_is_not_a_walk_in(client_factory):
    _, _, quote = _quote(client_factory, "wi-not", walk_in=False)
    assert quote["walk_in"] is False


def test_contractor_can_approve_for_a_walk_in(client_factory):
    c, contractor, quote = _quote(client_factory, "wi-appr")
    resp = c.post(f"/v1/quotations/{quote['quotation_id']}/approve", headers=_auth(contractor))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["decided_by"] == user_uuid("contractor-wi-appr")
    # replay is harmless and keeps the original decider
    again = c.post(f"/v1/quotations/{quote['quotation_id']}/approve", headers=_auth(contractor))
    assert again.status_code == 200 and again.json()["decided_by"] == body["decided_by"]


def test_contractor_can_reject_for_a_walk_in(client_factory):
    c, contractor, quote = _quote(client_factory, "wi-rej")
    resp = c.post(f"/v1/quotations/{quote['quotation_id']}/reject", headers=_auth(contractor))
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["decided_by"] == user_uuid("contractor-wi-rej")


def test_admin_can_approve_for_a_walk_in(client_factory):
    c, _, quote = _quote(client_factory, "wi-admin")
    admin = make_token("admin-1", "admin")
    resp = c.post(f"/v1/quotations/{quote['quotation_id']}/approve", headers=_auth(admin))
    assert resp.status_code == 200 and resp.json()["decided_by"] == user_uuid("admin-1")


def test_contractor_still_cannot_decide_for_an_app_customer(client_factory):
    c, contractor, quote = _quote(client_factory, "wi-app", walk_in=False)
    for action in ("approve", "reject"):
        resp = c.post(f"/v1/quotations/{quote['quotation_id']}/{action}", headers=_auth(contractor))
        assert resp.status_code == 403, action
    latest = c.get(f"/v1/quotations/job/{quote['job_id']}/latest", headers=_auth(contractor)).json()
    assert latest["status"] == "draft"


def test_a_different_contractor_cannot_decide_for_a_walk_in(client_factory):
    c, _, quote = _quote(client_factory, "wi-owner")
    other = make_token("contractor-someone-else", "contractor")
    for action in ("approve", "reject"):
        resp = c.post(f"/v1/quotations/{quote['quotation_id']}/{action}", headers=_auth(other))
        assert resp.status_code == 403, action


def test_resource_owner_cannot_decide(client_factory):
    c, _, quote = _quote(client_factory, "wi-ro")
    owner = make_token("owner-1", "resource_owner")
    resp = c.post(f"/v1/quotations/{quote['quotation_id']}/approve", headers=_auth(owner))
    assert resp.status_code == 403


def test_an_app_customer_cannot_decide_for_a_walk_in(client_factory):
    c, _, quote = _quote(client_factory, "wi-cust")
    someone = make_token("some-customer", "customer")
    resp = c.post(f"/v1/quotations/{quote['quotation_id']}/approve", headers=_auth(someone))
    assert resp.status_code == 403


def test_walk_in_flag_survives_a_revision_and_old_versions_stay_closed(client_factory):
    c, contractor, v1 = _quote(client_factory, "wi-rev")
    v2 = c.patch(
        f"/v1/quotations/{v1['quotation_id']}",
        json={"total_estimate": "99999"},
        headers=_auth(contractor),
    ).json()
    assert v2["walk_in"] is True and v2["customer_id"] == v1["customer_id"]
    old = c.post(f"/v1/quotations/{v1['quotation_id']}/approve", headers=_auth(contractor))
    assert old.status_code == 409 and old.json()["error"]["code"] == "QUOTATION_SUPERSEDED"
    ok = c.post(f"/v1/quotations/{v2['quotation_id']}/approve", headers=_auth(contractor))
    assert ok.status_code == 200


def test_an_approved_walk_in_quote_cannot_be_flipped_to_rejected(client_factory):
    c, contractor, quote = _quote(client_factory, "wi-bind")
    c.post(f"/v1/quotations/{quote['quotation_id']}/approve", headers=_auth(contractor))
    resp = c.post(f"/v1/quotations/{quote['quotation_id']}/reject", headers=_auth(contractor))
    assert resp.status_code == 409
