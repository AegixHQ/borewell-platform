import uuid
from decimal import Decimal

from tests.conftest import make_token, user_uuid

BASE_RULE = {
    "job_type": "residential",
    "base_rate_per_ft": 150,
    "casing_rate_per_ft": 80,
    "labour_flat_fee": 5000,
    "transport_flat_fee": 2000,
    "equipment_flat_fee": 3000,
    "installation_flat_fee": 4000,
    "margin_percent": 15,
    "minimum_job_charge": 20000,
    "assumed_depth_ft": 300,
    "depth_confidence_band_ft": 50,
    "depth_overage_rate_per_ft": 200,
}


def _setup_rule(client, contractor_id, **overrides):
    token = make_token(contractor_id, "contractor")
    payload = dict(BASE_RULE, **overrides)
    client.post("/v1/pricing-rules", json=payload, headers={"Authorization": f"Bearer {token}"})
    return token


def _quote_request(job_id=None, job_type="residential"):
    return {
        "job_id": job_id or str(uuid.uuid4()),
        "location": {"lat": 13.0827, "lng": 80.2707},
        "job_type": job_type,
    }


def test_generate_quotation_without_pricing_rule_fails_clearly(client):
    token = make_token("contractor-x", "contractor")
    resp = client.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PRICING_RULE_MISSING"


def test_generate_quotation_with_pricing_rule(client):
    token = _setup_rule(client, "contractor-y")
    resp = client.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["version"] == 1
    assert body["status"] == "draft"
    assert body["estimated_depth_range"] == {"min_ft": 250, "max_ft": 350, "confidence": "low"}
    # Compared as Decimal, not against raw string formatting or float - the
    # response field is now a numeric string (see schemas.QuotationResponse;
    # FastAPI serializes Decimal as a JSON string to avoid float round-trip
    # loss), so this is what actually verifies the value is exact, not just
    # that it happens to match a hardcoded string's formatting.
    assert Decimal(body["subtotal"]) == Decimal("83000.00")
    assert Decimal(body["margin_amount"]) == Decimal("12450.00")
    assert Decimal(body["total_estimate"]) == Decimal("95450.00")
    assert body["minimum_charge_applied"] is False
    assert len(body["line_items"]) == 6


def test_customer_cannot_generate_quotation(client):
    _setup_rule(client, "contractor-nogen")
    cust_token = make_token("cust-nogen", "customer")
    resp = client.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {cust_token}"}
    )
    assert resp.status_code == 403


def test_minimum_charge_is_enforced(client):
    token = _setup_rule(
        client,
        "contractor-z",
        job_type="agricultural",
        base_rate_per_ft=10,
        casing_rate_per_ft=5,
        labour_flat_fee=100,
        transport_flat_fee=100,
        equipment_flat_fee=100,
        installation_flat_fee=100,
        margin_percent=10,
        minimum_job_charge=50000,
        assumed_depth_ft=100,
    )
    resp = client.post(
        "/v1/quotations",
        json=_quote_request(job_type="agricultural"),
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert Decimal(body["total_estimate"]) == Decimal("50000")
    assert body["minimum_charge_applied"] is True
    # SRS section 11 acceptance criterion is a single compound statement:
    # never below minimum AND always depth range + confidence. The minimum-
    # charge path is exactly the edge case where a depth/confidence field
    # could get dropped by an early-return special case - assert it here,
    # not just in the general-case test below.
    assert "min_ft" in body["estimated_depth_range"]
    assert "max_ft" in body["estimated_depth_range"]
    assert body["estimated_depth_range"]["confidence"] in ("low", "medium", "high")


def test_editing_quotation_creates_new_version(client):
    token = _setup_rule(client, "contractor-edit")
    create_resp = client.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]
    job_id = create_resp.json()["job_id"]

    edit_resp = client.patch(
        f"/v1/quotations/{quotation_id}",
        json={"total_estimate": 99999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert edit_resp.status_code == 201
    body = edit_resp.json()
    assert body["version"] == 2
    assert Decimal(body["total_estimate"]) == Decimal("99999")
    assert body["job_id"] == job_id
    # original stays untouched - append-only versioning, not mutation
    original = client.get(
        f"/v1/quotations/{quotation_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert Decimal(original.json()["total_estimate"]) == Decimal("95450.00")


def test_other_contractor_cannot_edit_quotation(client):
    token = _setup_rule(client, "contractor-owner")
    create_resp = client.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]

    other_token = make_token("contractor-other", "contractor")
    resp = client.patch(
        f"/v1/quotations/{quotation_id}",
        json={"total_estimate": 1},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


def test_get_latest_quotation_for_job_returns_newest_version(client):
    token = _setup_rule(client, "contractor-latest")
    create_resp = client.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]
    job_id = create_resp.json()["job_id"]
    client.patch(
        f"/v1/quotations/{quotation_id}",
        json={"total_estimate": 88888},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = client.get(
        f"/v1/quotations/job/{job_id}/latest", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 2
    assert Decimal(resp.json()["total_estimate"]) == Decimal("88888")


def test_latest_quotation_404_when_none_exists(client):
    token = make_token("contractor-none", "contractor")
    resp = client.get(
        f"/v1/quotations/job/{uuid.uuid4()}/latest", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "QUOTATION_NOT_FOUND"


def test_customer_can_approve_quotation(client_factory):
    c = client_factory(customer_id=user_uuid("cust-appr"))
    token = _setup_rule(c, "contractor-appr")
    create_resp = c.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]

    cust_token = make_token("cust-appr", "customer")
    resp = c.post(
        f"/v1/quotations/{quotation_id}/approve", headers={"Authorization": f"Bearer {cust_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_customer_can_reject_quotation(client_factory):
    c = client_factory(customer_id=user_uuid("cust-rej"))
    token = _setup_rule(c, "contractor-rej")
    create_resp = c.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]

    cust_token = make_token("cust-rej", "customer")
    resp = c.post(
        f"/v1/quotations/{quotation_id}/reject", headers={"Authorization": f"Bearer {cust_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_contractor_cannot_approve_quotation(client):
    token = _setup_rule(client, "contractor-appr2")
    create_resp = client.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]

    resp = client.post(
        f"/v1/quotations/{quotation_id}/approve", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_get_nonexistent_quotation_404s(client):
    token = make_token("contractor-404", "contractor")
    resp = client.get(
        f"/v1/quotations/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


def test_resource_owner_cannot_generate_quotation(client):
    token = make_token("rigowner-2", "resource_owner")
    resp = client.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


# ---------- F-01 regression tests ----------
# Every one of these must fail (403/404/502) the way it says, or the
# ownership fix has regressed.


def test_owning_customer_can_view_quotation(client_factory):
    c = client_factory(customer_id=user_uuid("owner-cust"))
    token = _setup_rule(c, "contractor-owner-view")
    create_resp = c.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]

    owner_token = make_token("owner-cust", "customer")
    resp = c.get(
        f"/v1/quotations/{quotation_id}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp.status_code == 200


def test_different_customer_cannot_view_quotation(client_factory):
    c = client_factory(customer_id=user_uuid("real-owner"))
    token = _setup_rule(c, "contractor-idor-1")
    create_resp = c.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]

    attacker_token = make_token("not-the-owner", "customer")
    resp = c.get(
        f"/v1/quotations/{quotation_id}", headers={"Authorization": f"Bearer {attacker_token}"}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_different_customer_cannot_view_latest_quotation_for_job(client_factory):
    c = client_factory(customer_id=user_uuid("real-owner-2"))
    token = _setup_rule(c, "contractor-idor-2")
    job_id = str(uuid.uuid4())
    c.post(
        "/v1/quotations",
        json=_quote_request(job_id=job_id),
        headers={"Authorization": f"Bearer {token}"},
    )

    attacker_token = make_token("not-the-owner-2", "customer")
    resp = c.get(
        f"/v1/quotations/job/{job_id}/latest", headers={"Authorization": f"Bearer {attacker_token}"}
    )
    assert resp.status_code == 403


def test_different_customer_cannot_approve_quotation(client_factory):
    c = client_factory(customer_id=user_uuid("real-owner-3"))
    token = _setup_rule(c, "contractor-idor-3")
    create_resp = c.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]

    attacker_token = make_token("not-the-owner-3", "customer")
    resp = c.post(
        f"/v1/quotations/{quotation_id}/approve",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert resp.status_code == 403
    check = c.get(
        f"/v1/quotations/{quotation_id}",
        headers={"Authorization": f"Bearer {make_token('real-owner-3', 'customer')}"},
    )
    assert check.json()["status"] == "draft"


def test_different_customer_cannot_reject_quotation(client_factory):
    c = client_factory(customer_id=user_uuid("real-owner-4"))
    token = _setup_rule(c, "contractor-idor-4")
    create_resp = c.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]

    attacker_token = make_token("not-the-owner-4", "customer")
    resp = c.post(
        f"/v1/quotations/{quotation_id}/reject",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert resp.status_code == 403


def test_generate_quotation_for_nonexistent_job_fails(client_factory):
    def not_found_fetcher():
        def _fetch(job_id, auth_header):
            from app.jobs.job_client import JobNotFound

            raise JobNotFound("job not found")

        return _fetch

    c = client_factory(job_fetcher=not_found_fetcher)
    token = _setup_rule(c, "contractor-nojob")
    resp = c.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_generate_quotation_fails_closed_when_job_service_unreachable(client_factory):
    def unavailable_fetcher():
        def _fetch(job_id, auth_header):
            from app.jobs.job_client import JobServiceError

            raise JobServiceError("connection refused")

        return _fetch

    c = client_factory(job_fetcher=unavailable_fetcher)
    token = _setup_rule(c, "contractor-svcdown")
    resp = c.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "JOB_SERVICE_UNAVAILABLE"


def test_generate_quotation_uses_service_area_depth_when_matched(client_factory):
    """docs/adr/0004: when a pilot service area covers the job's location,
    the quotation uses that area's water-depth estimate at 'medium'
    confidence, instead of the contractor's flat assumed_depth_ft/'low'."""

    def matched_location_fetcher():
        def _fetch(lat, lng, auth_header):
            return {"estimated_water_depth_ft": 280.0, "confidence_band_ft": 40.0}

        return _fetch

    c = client_factory(location_fetcher=matched_location_fetcher)
    token = _setup_rule(
        c, "contractor-servicearea", assumed_depth_ft=1000, depth_confidence_band_ft=10
    )

    resp = c.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    body = resp.json()
    assert body["estimated_depth_range"]["confidence"] == "medium"
    assert body["estimated_depth_range"]["min_ft"] == 240
    assert body["estimated_depth_range"]["max_ft"] == 320


def test_generate_quotation_falls_back_to_flat_assumption_without_service_area_match(
    client_factory,
):
    """Default fake_location_fetcher() returns None (no coverage) - this
    is the expected outcome outside pilot villages and must reproduce
    exact pre-pilot MVP behavior: flat assumed_depth_ft, 'low' confidence."""
    c = client_factory()  # default location_fetcher returns None
    token = _setup_rule(
        c, "contractor-nolocation", assumed_depth_ft=300, depth_confidence_band_ft=50
    )

    resp = c.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    body = resp.json()
    assert body["estimated_depth_range"]["confidence"] == "low"
    assert body["estimated_depth_range"]["min_ft"] == 250
    assert body["estimated_depth_range"]["max_ft"] == 350
