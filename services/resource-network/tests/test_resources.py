from tests.conftest import make_token


def test_contractor_can_create_resource(client):
    token = make_token("contractor-1", "contractor")
    resp = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rotary Rig #1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "available"
    assert body["resource_type"] == "rig"


def test_customer_cannot_create_resource(client):
    token = make_token("cust-1", "customer")
    resp = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rotary Rig #1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_invalid_resource_type_rejected(client):
    token = make_token("contractor-2", "contractor")
    resp = client.post(
        "/v1/resources",
        json={"resource_type": "spaceship", "name": "Rig"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_list_resources_filters_by_own_contractor(client):
    token1 = make_token("contractor-a", "contractor")
    token2 = make_token("contractor-b", "contractor")
    client.post(
        "/v1/resources",
        json={"resource_type": "equipment", "name": "Compressor A"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    resp = client.get("/v1/resources", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_resources_status_filter(client):
    token = make_token("contractor-filter", "contractor")
    r1 = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rig X"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    client.post(
        "/v1/resources",
        json={"resource_type": "equipment", "name": "Pump Y"},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.patch(
        f"/v1/resources/{r1['resource_id']}",
        json={"status": "in_use"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get(
        "/v1/resources?status_filter=in_use", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Rig X"


def test_update_resource_status_through_lifecycle(client):
    token = make_token("contractor-lifecycle", "contractor")
    created = client.post(
        "/v1/resources",
        json={"resource_type": "labour", "name": "Crew A"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    resource_id = created["resource_id"]

    for new_status in ["reserved", "assigned", "in_use", "returned"]:
        resp = client.patch(
            f"/v1/resources/{resource_id}",
            json={"status": new_status},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == new_status


def test_invalid_status_rejected(client):
    token = make_token("contractor-badstatus", "contractor")
    created = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rig Z"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    resp = client.patch(
        f"/v1/resources/{created['resource_id']}",
        json={"status": "on_vacation"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_other_contractor_cannot_view_or_edit_resource(client):
    token = make_token("contractor-owner2", "contractor")
    created = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "Rig Private"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    other_token = make_token("contractor-other2", "contractor")

    get_resp = client.get(
        f"/v1/resources/{created['resource_id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert get_resp.status_code == 403

    patch_resp = client.patch(
        f"/v1/resources/{created['resource_id']}",
        json={"status": "in_use"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert patch_resp.status_code == 403


def test_get_nonexistent_resource_404s(client):
    import uuid as uuid_module

    token = make_token("contractor-404", "contractor")
    resp = client.get(
        f"/v1/resources/{uuid_module.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


def test_resource_owner_cannot_create_resource_yet(client):
    # Deliberately still rejected: this MVP's data model keys resources to
    # contractor_id only - there's no independent resource-owner-owned
    # inventory concept yet. Granting this role CRUD access before that
    # data model exists would let a resource_owner see an always-empty
    # list and call it "done," which is worse than not shipping it. Real
    # rig management (RFC 0001 section 7, Phase 1) needs a schema change
    # here, not just a role check - revisit this test when that lands.
    token = make_token("rigowner-1", "resource_owner")
    resp = client.post(
        "/v1/resources",
        json={"resource_type": "rig", "name": "My Rig"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
