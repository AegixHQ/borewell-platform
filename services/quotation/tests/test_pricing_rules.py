from tests.conftest import make_token

VALID_RULE = {
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


def test_contractor_can_create_pricing_rule(client):
    token = make_token("contractor-1", "contractor")
    resp = client.post(
        "/v1/pricing-rules", json=VALID_RULE, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["job_type"] == "residential"


def test_customer_cannot_create_pricing_rule(client):
    token = make_token("cust-1", "customer")
    resp = client.post(
        "/v1/pricing-rules", json=VALID_RULE, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_posting_same_job_type_twice_upserts_not_duplicates(client):
    token = make_token("contractor-2", "contractor")
    payload = dict(VALID_RULE, job_type="commercial")
    client.post("/v1/pricing-rules", json=payload, headers={"Authorization": f"Bearer {token}"})
    payload["base_rate_per_ft"] = 175
    client.post("/v1/pricing-rules", json=payload, headers={"Authorization": f"Bearer {token}"})

    resp = client.get("/v1/pricing-rules", headers={"Authorization": f"Bearer {token}"})
    rules = [r for r in resp.json() if r["job_type"] == "commercial"]
    assert len(rules) == 1
    assert rules[0]["base_rate_per_ft"] == 175


def test_invalid_margin_rejected(client):
    token = make_token("contractor-3", "contractor")
    payload = dict(VALID_RULE, margin_percent=150)
    resp = client.post(
        "/v1/pricing-rules", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


def test_negative_base_rate_rejected(client):
    token = make_token("contractor-4", "contractor")
    payload = dict(VALID_RULE, base_rate_per_ft=-10)
    resp = client.post(
        "/v1/pricing-rules", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


def test_resource_owner_cannot_create_pricing_rule(client):
    # Proves the claim that resource_owner is isolated from quotation's
    # engine, not just documented - see platform-spine's
    # test_resource_owner_can_register_and_login for where the role itself
    # is proven to work.
    token = make_token("rigowner-1", "resource_owner")
    resp = client.post(
        "/v1/pricing-rules", json=VALID_RULE, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
