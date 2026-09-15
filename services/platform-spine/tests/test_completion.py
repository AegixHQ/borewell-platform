"""
Tests for FR-TRACK-03 (log actual depth/cost) and FR-TRACK-04 (variance).

SRS section 11 acceptance criterion (verbatim): "Marking a job 'completion'
without actual cost logged is rejected; with it logged, the variance
calculation matches actual - quoted exactly."

The quotation_client.fetch_approved_quotation call is mocked via
unittest.mock.patch since there's no live quotation service in tests - the
same approach payments-data uses for its quotation fetcher dependency.
"""
from decimal import Decimal
from unittest.mock import patch

MOCK_QUOTATION = {
    "total_estimate": Decimal("80000.00"),
    "min_ft": 200.0,
    "max_ft": 250.0,
    "depth_overage_rate_per_ft": Decimal("150.00"),
}
MOCK_PATCH = "app.quotation_client.fetch_approved_quotation"


def _register_and_login(client, email, role):
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass12345678", "role": role},
    )
    resp = client.post("/v1/auth/login", json={"email": email, "password": "pass12345678"})
    return resp.json()["access_token"]


def _create_job_at_completion(client, cust_token, contractor_token):
    """Create a job and advance it all the way to 'completion' status."""
    job_resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.08, "lng": 80.27}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["job_id"]

    # Advance through every stage to 'completion' - the state machine is the
    # enforcement layer and must be satisfied even in tests (FR-JOB-03).
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


# ---- SRS section 11 core acceptance criterion ----

def test_completion_within_depth_range_computes_variance_exactly(client):
    """FR-TRACK-03 + FR-TRACK-04: with actual cost logged the variance
    matches actual_cost - quoted_total exactly (SRS section 11)."""
    cust = _register_and_login(client, "c1@example.com", "customer")
    cont = _register_and_login(client, "k1@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust, cont)

    with patch(MOCK_PATCH, return_value=MOCK_QUOTATION):
        resp = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 220.0, "actual_cost": 75000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )
    assert resp.status_code == 201
    body = resp.json()

    # Variance must match exactly - SRS section 11 acceptance criterion.
    assert Decimal(body["variance"]) == Decimal("75000.00") - Decimal("80000.00")
    assert Decimal(body["variance"]) == Decimal("-5000.00")
    assert body["depth_overage_ft"] == 0.0


def test_completion_requires_job_at_completion_status(client):
    """FR-TRACK-03 acceptance criterion: rejected if job isn't at 'completion'."""
    cust = _register_and_login(client, "c2@example.com", "customer")
    cont = _register_and_login(client, "k2@example.com", "contractor")
    job_resp = client.post(
        "/v1/jobs",
        json={"location": {"lat": 13.08, "lng": 80.27}, "job_type": "residential"},
        headers={"Authorization": f"Bearer {cust}"},
    )
    job_id = job_resp.json()["job_id"]
    # job is 'lead' - not at completion

    with patch(MOCK_PATCH, return_value=MOCK_QUOTATION):
        resp = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 220.0, "actual_cost": 75000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "JOB_NOT_AT_COMPLETION"


def test_completion_only_writable_once(client):
    """BR-04: never overwritten - second POST returns 409."""
    cust = _register_and_login(client, "c3@example.com", "customer")
    cont = _register_and_login(client, "k3@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust, cont)

    with patch(MOCK_PATCH, return_value=MOCK_QUOTATION):
        r1 = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 220.0, "actual_cost": 75000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )
        assert r1.status_code == 201

        r2 = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 230.0, "actual_cost": 90000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "ALREADY_COMPLETED"
    # Original record must be unchanged (BR-04: never overwritten)
    get_resp = client.get(
        f"/v1/jobs/{job_id}/completion/result",
        headers={"Authorization": f"Bearer {cont}"},
    )
    assert Decimal(get_resp.json()["actual_cost"]) == Decimal("75000.00")


def test_depth_overage_computed_when_actual_exceeds_max(client):
    """BR-05: depth_overage_ft is positive when actual > max_ft, and the
    overage charge is computed at the quotation's snapshotted per-foot
    rate (MOCK_QUOTATION's depth_overage_rate_per_ft: 150.00) - priced
    transparently, not silently added (SRS section 4's exact wording)."""
    cust = _register_and_login(client, "c4@example.com", "customer")
    cont = _register_and_login(client, "k4@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust, cont)

    # actual_depth_ft=280 > max_ft=250 from MOCK_QUOTATION -> overage=30ft
    # 30ft * 150.00/ft = 4500.00
    with patch(MOCK_PATCH, return_value=MOCK_QUOTATION):
        resp = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 280.0, "actual_cost": 95000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["depth_overage_ft"] == 30.0
    assert Decimal(body["depth_overage_charge"]) == Decimal("4500.00")


def test_no_overage_charge_when_actual_within_quoted_range(client):
    """The inverse case: actual depth within range -> zero overage feet
    AND zero charge, not just zero feet with an unverified charge."""
    cust = _register_and_login(client, "c-nooverage@example.com", "customer")
    cont = _register_and_login(client, "k-nooverage@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust, cont)

    with patch(MOCK_PATCH, return_value=MOCK_QUOTATION):
        resp = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 240.0, "actual_cost": 75000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["depth_overage_ft"] == 0.0
    assert Decimal(body["depth_overage_charge"]) == Decimal("0")


def test_completion_rejected_when_overage_occurs_but_rate_unavailable(client):
    """A quotation predating migration 0003 (depth_overage_rate_per_ft
    absent entirely, not just None) must not silently charge 0 for a real
    overage - that would look identical to 'no overage occurred', which is
    worse than an explicit, honest rejection (OVERAGE_RATE_UNAVAILABLE)."""
    cust = _register_and_login(client, "c-norate@example.com", "customer")
    cont = _register_and_login(client, "k-norate@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust, cont)

    old_style_quotation = {
        "total_estimate": Decimal("80000.00"),
        "min_ft": 200.0,
        "max_ft": 250.0,
        "depth_overage_rate_per_ft": None,
    }
    with patch(MOCK_PATCH, return_value=old_style_quotation):
        resp = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 280.0, "actual_cost": 95000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "OVERAGE_RATE_UNAVAILABLE"


def test_customer_can_read_own_completion_record(client):
    """FR-TRACK-04: customer can see variance on their own job."""
    cust = _register_and_login(client, "c5@example.com", "customer")
    cont = _register_and_login(client, "k5@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust, cont)

    with patch(MOCK_PATCH, return_value=MOCK_QUOTATION):
        client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 220.0, "actual_cost": 80000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )

    get_resp = client.get(
        f"/v1/jobs/{job_id}/completion/result",
        headers={"Authorization": f"Bearer {cust}"},
    )
    assert get_resp.status_code == 200
    # When actual == quoted, variance is 0.
    assert Decimal(get_resp.json()["variance"]) == Decimal("0.00")


def test_customer_cannot_read_another_customers_completion(client):
    """IDOR: customer A cannot read customer B's job completion."""
    cust_a = _register_and_login(client, "a@example.com", "customer")
    cust_b = _register_and_login(client, "b@example.com", "customer")
    cont = _register_and_login(client, "k6@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust_a, cont)

    with patch(MOCK_PATCH, return_value=MOCK_QUOTATION):
        client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 220.0, "actual_cost": 75000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )

    resp = client.get(
        f"/v1/jobs/{job_id}/completion/result",
        headers={"Authorization": f"Bearer {cust_b}"},
    )
    assert resp.status_code == 403


def test_no_quotation_blocks_completion(client):
    """Missing approved quotation returns 400, not 500."""
    from app.quotation_client import QuotationNotFound

    cust = _register_and_login(client, "c7@example.com", "customer")
    cont = _register_and_login(client, "k7@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust, cont)

    with patch(MOCK_PATCH, side_effect=QuotationNotFound("no quotation")):
        resp = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 220.0, "actual_cost": 75000.0},
            headers={"Authorization": f"Bearer {cont}"},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "NO_APPROVED_QUOTATION"


def test_customer_role_cannot_log_completion(client):
    """FR-TRACK-03: only contractor/admin may log completion."""
    cust = _register_and_login(client, "c8@example.com", "customer")
    cont = _register_and_login(client, "k8@example.com", "contractor")
    job_id = _create_job_at_completion(client, cust, cont)

    with patch(MOCK_PATCH, return_value=MOCK_QUOTATION):
        resp = client.post(
            f"/v1/jobs/{job_id}/completion",
            json={"actual_depth_ft": 220.0, "actual_cost": 75000.0},
            headers={"Authorization": f"Bearer {cust}"},
        )
    assert resp.status_code == 403
