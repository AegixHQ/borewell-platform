"""
Resource CRUD, owned by resource_owner (marketplace model - see
docs/adr/0004 for the pivot from the earlier single-contractor-owns-its-
own-fleet design). A contractor never owns a resource directly; they
request to book one (see test_matching.py for booking-request tests).
"""
from tests.conftest import make_token


def test_resource_owner_can_create_resource(client):
    token = make_token("owner-1", "resource_owner")
    resp = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rotary Rig #1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["resource_type"] == "rig"
    assert body["status"] == "available"


def test_customer_cannot_create_resource(client):
    token = make_token("cust-1", "customer")
    resp = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rotary Rig #1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_contractor_cannot_create_resource(client):
    # The pivot's whole point: a contractor books, they don't own.
    token = make_token("contractor-cannotcreate", "contractor")
    resp = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rotary Rig #1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_customer_cannot_list_resources(client):
    token = make_token("cust-list", "customer")
    resp = client.get("/v1/resources", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_customer_cannot_get_single_resource(client):
    owner_token = make_token("owner-getcheck", "resource_owner")
    created = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rig For Get Check"},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()

    cust_token = make_token("cust-get", "customer")
    resp = client.get(
        f"/v1/resources/{created['resource_id']}",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert resp.status_code == 403


def test_customer_cannot_update_resource_status(client):
    owner_token = make_token("owner-patchcheck", "resource_owner")
    created = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rig For Patch Check"},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()

    cust_token = make_token("cust-patch", "customer")
    resp = client.patch(
        f"/v1/resources/{created['resource_id']}",
        json={"status": "in_use"},
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert resp.status_code == 403


def test_invalid_resource_type_rejected(client):
    token = make_token("owner-2", "resource_owner")
    resp = client.post(
        "/v1/resources",
        json={"resource_type": "bulldozer", "name": "Not A Real Type"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_list_resources_filters_by_own_owner(client):
    token_a = make_token("owner-a", "resource_owner")
    token_b = make_token("owner-b", "resource_owner")
    client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Owner A Rig"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Owner B Rig"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    resp = client.get("/v1/resources", headers={"Authorization": f"Bearer {token_a}"})
    names = [r["name"] for r in resp.json()]
    assert names == ["Owner A Rig"]


def test_list_resources_status_filter(client):
    token = make_token("owner-3", "resource_owner")
    r1 = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Available Rig"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    r2 = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Busy Rig"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    client.patch(
        f"/v1/resources/{r2['resource_id']}",
        json={"status": "in_use"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = client.get(
        "/v1/resources?status_filter=available", headers={"Authorization": f"Bearer {token}"}
    )
    names = [r["name"] for r in resp.json()]
    assert names == ["Available Rig"]
    assert r1["resource_id"] != r2["resource_id"]


def test_update_resource_status_through_lifecycle(client):
    token = make_token("owner-4", "resource_owner")
    created = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Lifecycle Rig"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    for new_status in ("reserved", "assigned", "in_use", "returned"):
        resp = client.patch(
            f"/v1/resources/{created['resource_id']}",
            json={"status": new_status},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == new_status


def test_invalid_status_rejected(client):
    token = make_token("owner-5", "resource_owner")
    created = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Status Check Rig"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    resp = client.patch(
        f"/v1/resources/{created['resource_id']}",
        json={"status": "on_fire"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_other_owner_cannot_view_or_edit_resource(client):
    owner_a = make_token("owner-6a", "resource_owner")
    owner_b = make_token("owner-6b", "resource_owner")
    created = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Owner A's Rig"},
        headers={"Authorization": f"Bearer {owner_a}"},
    ).json()

    get_resp = client.get(
        f"/v1/resources/{created['resource_id']}",
        headers={"Authorization": f"Bearer {owner_b}"},
    )
    assert get_resp.status_code == 403

    patch_resp = client.patch(
        f"/v1/resources/{created['resource_id']}",
        json={"status": "in_use"},
        headers={"Authorization": f"Bearer {owner_b}"},
    )
    assert patch_resp.status_code == 403


def test_get_nonexistent_resource_404s(client):
    token = make_token("owner-7", "resource_owner")
    resp = client.get(
        "/v1/resources/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
