"""Tests for POST /v1/resources/match (cross-owner marketplace search),
POST /v1/bookings (contractor requests, owner accepts/rejects - Zomato-
style flow, docs/adr/0004), and /v1/service-areas (pilot water-depth
reference data)."""
from decimal import Decimal

from tests.conftest import make_token

# Real Madurai-district-area coordinates for realistic distance testing.
MADURAI = (9.9252, 78.1198)
VIRUDHUNAGAR = (9.5851, 77.9624)
CHENNAI = (13.0827, 80.2707)  # deliberately far away, for "nearest" ranking


def _create_resource(client, owner_token, **overrides):
    payload = {
        "resource_type": "rig",
        "name": "Test Rig",
        "lat": MADURAI[0],
        "lng": MADURAI[1],
        "hourly_rate": "850.00",
        "vehicle_type": "DTH Rig - Truck Mounted",
    }
    payload.update(overrides)
    return client.post(
        "/v1/resources", json=payload, headers={"Authorization": f"Bearer {owner_token}"}
    ).json()


# ---------- POST /v1/resources/match: cross-owner marketplace search ----------


def test_match_searches_across_all_owners_not_just_one(client):
    # The core of the marketplace pivot: two DIFFERENT owners' resources
    # both show up to a searching contractor.
    owner_a = make_token("owner-match-a", "resource_owner")
    owner_b = make_token("owner-match-b", "resource_owner")
    _create_resource(client, owner_a, name="Owner A's Rig")
    _create_resource(client, owner_b, name="Owner B's Rig")

    contractor = make_token("contractor-match1", "contractor")
    resp = client.post(
        "/v1/resources/match",
        json={"lat": VIRUDHUNAGAR[0], "lng": VIRUDHUNAGAR[1]},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()}
    assert names == {"Owner A's Rig", "Owner B's Rig"}


def test_match_ranks_by_distance_nearest_first(client):
    owner = make_token("owner-match2", "resource_owner")
    near = _create_resource(client, owner, name="Near Rig", lat=MADURAI[0], lng=MADURAI[1])
    far = _create_resource(client, owner, name="Far Rig", lat=CHENNAI[0], lng=CHENNAI[1])

    contractor = make_token("contractor-match2", "contractor")
    resp = client.post(
        "/v1/resources/match",
        json={"lat": VIRUDHUNAGAR[0], "lng": VIRUDHUNAGAR[1]},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    body = resp.json()
    assert len(body) == 2
    assert body[0]["resource_id"] == near["resource_id"]
    assert body[1]["resource_id"] == far["resource_id"]
    assert body[0]["distance_km"] < body[1]["distance_km"]


def test_match_excludes_resources_without_location(client):
    owner = make_token("owner-match3", "resource_owner")
    _create_resource(client, owner, name="Located Rig")
    client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "No Location Rig"},  # no lat/lng
        headers={"Authorization": f"Bearer {owner}"},
    )

    contractor = make_token("contractor-match3", "contractor")
    resp = client.post(
        "/v1/resources/match",
        json={"lat": VIRUDHUNAGAR[0], "lng": VIRUDHUNAGAR[1]},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Located Rig"


def test_match_excludes_unavailable_resources(client):
    owner = make_token("owner-match4", "resource_owner")
    created = _create_resource(client, owner, name="Busy Rig")
    client.patch(
        f"/v1/resources/{created['resource_id']}",
        json={"status": "in_use"},
        headers={"Authorization": f"Bearer {owner}"},
    )

    contractor = make_token("contractor-match4", "contractor")
    resp = client.post(
        "/v1/resources/match",
        json={"lat": VIRUDHUNAGAR[0], "lng": VIRUDHUNAGAR[1]},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    assert resp.json() == []


def test_match_respects_max_results(client):
    owner = make_token("owner-match5", "resource_owner")
    for i in range(7):
        _create_resource(client, owner, name=f"Rig {i}")

    contractor = make_token("contractor-match5", "contractor")
    resp = client.post(
        "/v1/resources/match",
        json={"lat": VIRUDHUNAGAR[0], "lng": VIRUDHUNAGAR[1], "max_results": 3},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    assert len(resp.json()) == 3


def test_match_filters_by_resource_type(client):
    owner = make_token("owner-match6", "resource_owner")
    _create_resource(client, owner, name="A Rig", resource_type="rig")
    _create_resource(client, owner, name="An Equipment", resource_type="equipment")

    contractor = make_token("contractor-match6", "contractor")
    resp = client.post(
        "/v1/resources/match",
        json={"lat": VIRUDHUNAGAR[0], "lng": VIRUDHUNAGAR[1], "resource_type": "equipment"},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    body = resp.json()
    assert len(body) == 1
    assert body[0]["resource_type"] == "equipment"


def test_customer_cannot_call_match(client):
    token = make_token("cust-match", "customer")
    resp = client.post(
        "/v1/resources/match",
        json={"lat": VIRUDHUNAGAR[0], "lng": VIRUDHUNAGAR[1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_resource_owner_cannot_call_match(client):
    # Match is the contractor's search tool, not the owner's.
    token = make_token("owner-callmatch", "resource_owner")
    resp = client.post(
        "/v1/resources/match",
        json={"lat": VIRUDHUNAGAR[0], "lng": VIRUDHUNAGAR[1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_match_result_includes_hourly_rate_and_vehicle_type(client):
    owner = make_token("owner-match7", "resource_owner")
    _create_resource(
        client, owner, name="Priced Rig", hourly_rate="1250.50", vehicle_type="Rotary Rig"
    )

    contractor = make_token("contractor-match7", "contractor")
    resp = client.post(
        "/v1/resources/match",
        json={"lat": VIRUDHUNAGAR[0], "lng": VIRUDHUNAGAR[1]},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    body = resp.json()[0]
    assert Decimal(body["hourly_rate"]) == Decimal("1250.50")
    assert body["vehicle_type"] == "Rotary Rig"


# ---------- POST /v1/bookings: contractor requests, owner accepts/rejects ----------


def test_contractor_can_request_booking(client):
    owner = make_token("owner-book1", "resource_owner")
    resource = _create_resource(client, owner, name="Bookable Rig")

    contractor = make_token("contractor-book1", "contractor")
    resp = client.post(
        "/v1/bookings",
        json={"resource_id": resource["resource_id"], "message": "Need this for a job tomorrow"},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["resource_id"] == resource["resource_id"]


def test_booking_request_rejected_if_resource_not_available(client):
    owner = make_token("owner-book2", "resource_owner")
    resource = _create_resource(client, owner, name="Busy Rig")
    client.patch(
        f"/v1/resources/{resource['resource_id']}",
        json={"status": "in_use"},
        headers={"Authorization": f"Bearer {owner}"},
    )

    contractor = make_token("contractor-book2", "contractor")
    resp = client.post(
        "/v1/bookings",
        json={"resource_id": resource["resource_id"]},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_AVAILABLE"


def test_second_booking_request_on_same_resource_conflicts(client):
    owner = make_token("owner-book3", "resource_owner")
    resource = _create_resource(client, owner, name="Popular Rig")

    contractor_a = make_token("contractor-book3a", "contractor")
    contractor_b = make_token("contractor-book3b", "contractor")

    r1 = client.post(
        "/v1/bookings",
        json={"resource_id": resource["resource_id"]},
        headers={"Authorization": f"Bearer {contractor_a}"},
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/v1/bookings",
        json={"resource_id": resource["resource_id"]},
        headers={"Authorization": f"Bearer {contractor_b}"},
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "RESOURCE_ALREADY_REQUESTED"


def test_owner_can_accept_booking_and_resource_becomes_reserved(client):
    owner = make_token("owner-book4", "resource_owner")
    resource = _create_resource(client, owner, name="Acceptable Rig")

    contractor = make_token("contractor-book4", "contractor")
    booking = client.post(
        "/v1/bookings",
        json={"resource_id": resource["resource_id"]},
        headers={"Authorization": f"Bearer {contractor}"},
    ).json()

    resp = client.post(
        f"/v1/bookings/{booking['booking_id']}/accept",
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    resource_check = client.get(
        f"/v1/resources/{resource['resource_id']}", headers={"Authorization": f"Bearer {owner}"}
    )
    assert resource_check.json()["status"] == "reserved"


def test_owner_can_reject_booking_resource_stays_available(client):
    owner = make_token("owner-book5", "resource_owner")
    resource = _create_resource(client, owner, name="Rejectable Rig")

    contractor = make_token("contractor-book5", "contractor")
    booking = client.post(
        "/v1/bookings",
        json={"resource_id": resource["resource_id"]},
        headers={"Authorization": f"Bearer {contractor}"},
    ).json()

    resp = client.post(
        f"/v1/bookings/{booking['booking_id']}/reject",
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    resource_check = client.get(
        f"/v1/resources/{resource['resource_id']}", headers={"Authorization": f"Bearer {owner}"}
    )
    assert resource_check.json()["status"] == "available"


def test_other_owner_cannot_accept_booking_on_someone_elses_resource(client):
    owner_a = make_token("owner-book6a", "resource_owner")
    owner_b = make_token("owner-book6b", "resource_owner")
    resource = _create_resource(client, owner_a, name="Owner A's Rig")

    contractor = make_token("contractor-book6", "contractor")
    booking = client.post(
        "/v1/bookings",
        json={"resource_id": resource["resource_id"]},
        headers={"Authorization": f"Bearer {contractor}"},
    ).json()

    resp = client.post(
        f"/v1/bookings/{booking['booking_id']}/accept",
        headers={"Authorization": f"Bearer {owner_b}"},
    )
    assert resp.status_code == 403


def test_cannot_accept_already_resolved_booking(client):
    owner = make_token("owner-book7", "resource_owner")
    resource = _create_resource(client, owner, name="Once Rig")

    contractor = make_token("contractor-book7", "contractor")
    booking = client.post(
        "/v1/bookings",
        json={"resource_id": resource["resource_id"]},
        headers={"Authorization": f"Bearer {contractor}"},
    ).json()

    client.post(
        f"/v1/bookings/{booking['booking_id']}/accept",
        headers={"Authorization": f"Bearer {owner}"},
    )
    second_attempt = client.post(
        f"/v1/bookings/{booking['booking_id']}/reject",
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert second_attempt.status_code == 409
    assert second_attempt.json()["error"]["code"] == "BOOKING_ALREADY_RESOLVED"


def test_resource_owner_sees_only_requests_on_own_resources(client):
    owner_a = make_token("owner-book8a", "resource_owner")
    owner_b = make_token("owner-book8b", "resource_owner")
    resource_a = _create_resource(client, owner_a, name="A's Rig")
    resource_b = _create_resource(client, owner_b, name="B's Rig")

    contractor = make_token("contractor-book8", "contractor")
    client.post(
        "/v1/bookings",
        json={"resource_id": resource_a["resource_id"]},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    client.post(
        "/v1/bookings",
        json={"resource_id": resource_b["resource_id"]},
        headers={"Authorization": f"Bearer {contractor}"},
    )

    resp = client.get("/v1/bookings", headers={"Authorization": f"Bearer {owner_a}"})
    body = resp.json()
    assert len(body) == 1
    assert body[0]["resource_id"] == resource_a["resource_id"]


def test_contractor_sees_only_own_requests(client):
    owner = make_token("owner-book9", "resource_owner")
    resource = _create_resource(client, owner, name="Shared Rig Owner's Rig")

    contractor_a = make_token("contractor-book9a", "contractor")
    contractor_b = make_token("contractor-book9b", "contractor")
    client.post(
        "/v1/bookings",
        json={"resource_id": resource["resource_id"]},
        headers={"Authorization": f"Bearer {contractor_a}"},
    )

    resp = client.get("/v1/bookings", headers={"Authorization": f"Bearer {contractor_b}"})
    assert resp.json() == []


def test_customer_cannot_access_bookings(client):
    token = make_token("cust-bookings", "customer")
    resp = client.get("/v1/bookings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_booking_nonexistent_resource_404s(client):
    contractor = make_token("contractor-book10", "contractor")
    resp = client.post(
        "/v1/bookings",
        json={"resource_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": f"Bearer {contractor}"},
    )
    assert resp.status_code == 404


# ---------- service areas ----------


def test_contractor_can_create_service_area(client):
    token = make_token("contractor-sa1", "contractor")
    resp = client.post(
        "/v1/service-areas",
        json={
            "name": "Virudhunagar",
            "district": "Virudhunagar",
            "state": "Tamil Nadu",
            "center_lat": VIRUDHUNAGAR[0],
            "center_lng": VIRUDHUNAGAR[1],
            "radius_km": 15,
            "estimated_water_depth_ft": 280,
            "confidence_band_ft": 40,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Virudhunagar"
    assert body["source"] == "contractor_estimate"


def test_posting_same_area_twice_upserts_not_duplicates(client):
    token = make_token("contractor-sa2", "contractor")
    payload = {
        "name": "Madurai City",
        "district": "Madurai",
        "state": "Tamil Nadu",
        "center_lat": MADURAI[0],
        "center_lng": MADURAI[1],
        "radius_km": 10,
        "estimated_water_depth_ft": 300,
        "confidence_band_ft": 30,
    }
    client.post("/v1/service-areas", json=payload, headers={"Authorization": f"Bearer {token}"})
    payload["estimated_water_depth_ft"] = 320
    client.post("/v1/service-areas", json=payload, headers={"Authorization": f"Bearer {token}"})

    resp = client.get("/v1/service-areas", headers={"Authorization": f"Bearer {token}"})
    matching = [a for a in resp.json() if a["name"] == "Madurai City"]
    assert len(matching) == 1
    assert matching[0]["estimated_water_depth_ft"] == 320


def test_customer_cannot_create_service_area(client):
    token = make_token("cust-sa", "customer")
    resp = client.post(
        "/v1/service-areas",
        json={
            "name": "Test", "district": "Test", "state": "Tamil Nadu",
            "center_lat": 9.0, "center_lng": 78.0, "radius_km": 10,
            "estimated_water_depth_ft": 250, "confidence_band_ft": 30,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_lookup_finds_covering_area(client):
    token = make_token("contractor-sa3", "contractor")
    client.post(
        "/v1/service-areas",
        json={
            "name": "Virudhunagar Lookup Test",
            "district": "Virudhunagar",
            "state": "Tamil Nadu",
            "center_lat": VIRUDHUNAGAR[0],
            "center_lng": VIRUDHUNAGAR[1],
            "radius_km": 15,
            "estimated_water_depth_ft": 280,
            "confidence_band_ft": 40,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get(
        f"/v1/service-areas/lookup?lat={VIRUDHUNAGAR[0]}&lng={VIRUDHUNAGAR[1]}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["estimated_water_depth_ft"] == 280


def test_lookup_returns_404_far_from_any_area(client):
    token = make_token("contractor-sa4", "contractor")
    client.post(
        "/v1/service-areas",
        json={
            "name": "Small Area",
            "district": "Virudhunagar",
            "state": "Tamil Nadu",
            "center_lat": VIRUDHUNAGAR[0],
            "center_lng": VIRUDHUNAGAR[1],
            "radius_km": 5,
            "estimated_water_depth_ft": 280,
            "confidence_band_ft": 40,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # 404 outside coverage is the EXPECTED behavior per the endpoint's own
    # doc comment - not an error case being tolerated, the actual contract.
    resp = client.get(
        f"/v1/service-areas/lookup?lat={CHENNAI[0]}&lng={CHENNAI[1]}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NO_SERVICE_AREA_COVERAGE"


def test_lookup_picks_nearest_when_areas_overlap(client):
    token = make_token("contractor-sa5", "contractor")
    client.post(
        "/v1/service-areas",
        json={
            "name": "Wide Area", "district": "Madurai", "state": "Tamil Nadu",
            "center_lat": MADURAI[0] + 0.3, "center_lng": MADURAI[1] + 0.3,
            "radius_km": 60, "estimated_water_depth_ft": 400, "confidence_band_ft": 50,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/v1/service-areas",
        json={
            "name": "Precise Area", "district": "Madurai", "state": "Tamil Nadu",
            "center_lat": MADURAI[0], "center_lng": MADURAI[1],
            "radius_km": 10, "estimated_water_depth_ft": 300, "confidence_band_ft": 20,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get(
        f"/v1/service-areas/lookup?lat={MADURAI[0]}&lng={MADURAI[1]}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["name"] == "Precise Area"
