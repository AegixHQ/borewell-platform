"""Free-text fields are bounded, and the service-area list needs a login."""

from tests.conftest import make_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_service_area_list_requires_authentication(client):
    assert client.get("/v1/service-areas").status_code == 401


def test_service_area_list_is_available_to_every_authenticated_role(client):
    for role in ("customer", "contractor", "admin", "resource_owner"):
        resp = client.get("/v1/service-areas", headers=_auth(make_token(f"{role}-1", role)))
        assert resp.status_code == 200, role


def test_resource_free_text_fields_are_bounded(client):
    token = make_token("owner-1", "resource_owner")
    base = {"resource_type": "rig", "name": "Rig A"}
    assert client.post("/v1/resources", json=base, headers=_auth(token)).status_code == 201
    for field, too_long in (("name", "n" * 121), ("notes", "x" * 1001), ("vehicle_type", "v" * 61)):
        resp = client.post("/v1/resources", json={**base, field: too_long}, headers=_auth(token))
        assert resp.status_code == 422, field


def test_service_area_text_fields_are_bounded(client):
    token = make_token("admin-1", "admin")
    area = {
        "name": "Village",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "center_lat": 13.0,
        "center_lng": 80.2,
        "radius_km": 5,
        "estimated_water_depth_ft": 300,
        "confidence_band_ft": 40,
    }
    assert client.post("/v1/service-areas", json=area, headers=_auth(token)).status_code == 201
    for field in ("name", "district", "state"):
        resp = client.post(
            "/v1/service-areas", json={**area, field: "z" * 500}, headers=_auth(token)
        )
        assert resp.status_code == 422, field
