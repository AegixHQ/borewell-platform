import uuid

from tests.conftest import make_token

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
    assert body["subtotal"] == 83000
    assert body["margin_amount"] == 12450
    assert body["total_estimate"] == 95450
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
    assert body["total_estimate"] == 50000
    assert body["minimum_charge_applied"] is True


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
    assert body["total_estimate"] == 99999
    assert body["job_id"] == job_id
    # original stays untouched - append-only versioning, not mutation
    original = client.get(
        f"/v1/quotations/{quotation_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert original.json()["total_estimate"] == 95450


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
    assert resp.json()["total_estimate"] == 88888


def test_latest_quotation_404_when_none_exists(client):
    token = make_token("contractor-none", "contractor")
    resp = client.get(
        f"/v1/quotations/job/{uuid.uuid4()}/latest", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "QUOTATION_NOT_FOUND"


def test_customer_can_approve_quotation(client):
    token = _setup_rule(client, "contractor-appr")
    create_resp = client.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]

    cust_token = make_token("cust-appr", "customer")
    resp = client.post(
        f"/v1/quotations/{quotation_id}/approve", headers={"Authorization": f"Bearer {cust_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_customer_can_reject_quotation(client):
    token = _setup_rule(client, "contractor-rej")
    create_resp = client.post(
        "/v1/quotations", json=_quote_request(), headers={"Authorization": f"Bearer {token}"}
    )
    quotation_id = create_resp.json()["quotation_id"]

    cust_token = make_token("cust-rej", "customer")
    resp = client.post(
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
