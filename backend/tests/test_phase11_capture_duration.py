from test_phase2_api import create_inspection, login, seed_identity_set


def test_admin_configures_capture_duration_and_inspector_receives_it(client, db):
    identities = seed_identity_set(db)
    admin_headers = login(client, identities["admin_a"])
    inspector_headers = login(client, identities["inspector_a"])

    created = create_inspection(client, admin_headers, captureDurationSeconds=45)
    assert created["captureDurationSeconds"] == 45

    assigned = client.post(
        f"/api/v1/inspections/{created['id']}/assign",
        headers=admin_headers,
        json={"inspectorId": str(identities["profile_a"].id)},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["captureDurationSeconds"] == 45

    listing = client.get("/api/v1/inspections", headers=inspector_headers)
    assert listing.status_code == 200, listing.text
    item = next(row for row in listing.json()["items"] if row["id"] == created["id"])
    assert item["captureDurationSeconds"] == 45

    updated = client.patch(
        f"/api/v1/inspections/{created['id']}",
        headers=admin_headers,
        json={"captureDurationSeconds": 63},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["captureDurationSeconds"] == 63


def test_capture_duration_validation(client, db):
    identities = seed_identity_set(db)
    headers = login(client, identities["admin_a"])

    custom = create_inspection(client, headers, captureDurationSeconds=75)
    assert custom["captureDurationSeconds"] == 75

    too_short = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={
            "title": "Short capture",
            "inspectionType": "GENERAL",
            "location": {"latitude": 22.5726, "longitude": 88.3639},
            "allowedRadiusMeters": 100,
            "captureDurationSeconds": 9,
            "deadline": "2099-01-01T00:00:00Z",
            "priority": "MEDIUM",
        },
    )
    assert too_short.status_code == 422

    too_long = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={
            "title": "Long capture",
            "inspectionType": "GENERAL",
            "location": {"latitude": 22.5726, "longitude": 88.3639},
            "allowedRadiusMeters": 100,
            "captureDurationSeconds": 76,
            "deadline": "2099-01-01T00:00:00Z",
            "priority": "MEDIUM",
        },
    )
    assert too_long.status_code == 422
