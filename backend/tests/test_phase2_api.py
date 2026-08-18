import uuid
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.models import (
    AuditLog,
    InspectionAssignment,
    Inspector,
    Organization,
    User,
    UserRole,
)

PASSWORD = "SiteProofTest!42"


def seed_user(db, org, *, email, name, role, active=True, inspector_active=True):
    user = User(
        organization_id=org.id,
        email=email,
        full_name=name,
        hashed_password=hash_password(PASSWORD),
        role=role,
        is_active=active,
    )
    db.add(user)
    db.flush()
    inspector = None
    if role == UserRole.INSPECTOR:
        inspector = Inspector(
            organization_id=org.id,
            user_id=user.id,
            employee_code=f"EMP-{str(user.id)[:8]}",
            active=inspector_active,
        )
        db.add(inspector)
        db.flush()
    return user, inspector


def seed_identity_set(db):
    org_a = Organization(name=f"Authority A {uuid.uuid4()}")
    org_b = Organization(name=f"Authority B {uuid.uuid4()}")
    db.add_all([org_a, org_b])
    db.flush()
    admin_a, _ = seed_user(
        db, org_a, email=f"admin-a-{uuid.uuid4()}@example.com", name="Admin A", role=UserRole.ADMIN
    )
    admin_b, _ = seed_user(
        db, org_b, email=f"admin-b-{uuid.uuid4()}@example.com", name="Admin B", role=UserRole.ADMIN
    )
    inspector_a, profile_a = seed_user(
        db, org_a, email=f"inspector-a-{uuid.uuid4()}@example.com", name="Inspector A", role=UserRole.INSPECTOR
    )
    inspector_a2, profile_a2 = seed_user(
        db, org_a, email=f"inspector-a2-{uuid.uuid4()}@example.com", name="Inspector A2", role=UserRole.INSPECTOR
    )
    inspector_b, profile_b = seed_user(
        db, org_b, email=f"inspector-b-{uuid.uuid4()}@example.com", name="Inspector B", role=UserRole.INSPECTOR
    )
    db.commit()
    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "inspector_a": inspector_a,
        "profile_a": profile_a,
        "inspector_a2": inspector_a2,
        "profile_a2": profile_a2,
        "inspector_b": inspector_b,
        "profile_b": profile_b,
    }


def login(client, user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def inspection_payload(**overrides):
    payload = {
        "title": "Verify repaired pothole",
        "description": "Confirm the road repair has been completed.",
        "inspectionType": "ROAD_REPAIR",
        "location": {
            "latitude": 22.5726,
            "longitude": 88.3639,
            "name": "Central Avenue",
            "address": "Kolkata, West Bengal",
        },
        "allowedRadiusMeters": 100,
        "deadline": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "priority": "HIGH",
        "instructions": "Capture the repaired road surface and surrounding area.",
    }
    payload.update(overrides)
    return payload


def create_inspection(client, headers, **overrides):
    response = client.post(
        "/api/v1/inspections", headers=headers, json=inspection_payload(**overrides)
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_phase2_end_to_end_admin_to_inspector(client, db):
    identities = seed_identity_set(db)
    admin_headers = login(client, identities["admin_a"])
    inspector_headers = login(client, identities["inspector_a"])

    created = create_inspection(client, admin_headers)
    assert created["status"] == "DRAFT"

    assigned = client.post(
        f"/api/v1/inspections/{created['id']}/assign",
        headers=admin_headers,
        json={"inspectorId": str(identities["profile_a"].id)},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "ASSIGNED"

    inspector_list = client.get("/api/v1/inspections", headers=inspector_headers)
    assert inspector_list.status_code == 200
    assert [item["id"] for item in inspector_list.json()["items"]] == [created["id"]]

    acknowledged = client.post(
        f"/api/v1/inspections/{created['id']}/acknowledge", headers=inspector_headers
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["status"] == "ACKNOWLEDGED"

    ready = client.post(
        f"/api/v1/inspections/{created['id']}/ready", headers=inspector_headers
    )
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "READY"

    detail = client.get(f"/api/v1/inspections/{created['id']}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "READY"
    actions = [row.action for row in db.query(AuditLog).all()]
    assert actions == [
        "INSPECTION_CREATED",
        "INSPECTION_ASSIGNED",
        "INSPECTION_ACKNOWLEDGED",
        "INSPECTION_READY",
    ]


def test_invalid_coordinates_radius_and_past_deadline(client, db):
    identities = seed_identity_set(db)
    headers = login(client, identities["admin_a"])

    invalid_lat = inspection_payload()
    invalid_lat["location"]["latitude"] = 91
    response = client.post("/api/v1/inspections", headers=headers, json=invalid_lat)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_lon = inspection_payload()
    invalid_lon["location"]["longitude"] = -181
    assert client.post("/api/v1/inspections", headers=headers, json=invalid_lon).status_code == 422

    invalid_radius = inspection_payload(allowedRadiusMeters=5)
    assert client.post("/api/v1/inspections", headers=headers, json=invalid_radius).status_code == 422

    past = inspection_payload(deadline=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    assert client.post("/api/v1/inspections", headers=headers, json=past).status_code == 422


def test_organization_and_inspector_isolation(client, db):
    identities = seed_identity_set(db)
    admin_a_headers = login(client, identities["admin_a"])
    admin_b_headers = login(client, identities["admin_b"])
    inspector_a2_headers = login(client, identities["inspector_a2"])
    created = create_inspection(client, admin_a_headers)
    client.post(
        f"/api/v1/inspections/{created['id']}/assign",
        headers=admin_a_headers,
        json={"inspectorId": str(identities["profile_a"].id)},
    )

    assert client.get(f"/api/v1/inspections/{created['id']}", headers=admin_b_headers).status_code == 404
    assert client.get(f"/api/v1/inspections/{created['id']}", headers=inspector_a2_headers).status_code == 404


def test_cross_org_and_unauthorized_assignment_rejected(client, db):
    identities = seed_identity_set(db)
    admin_headers = login(client, identities["admin_a"])
    inspector_headers = login(client, identities["inspector_a"])
    created = create_inspection(client, admin_headers)

    cross_org = client.post(
        f"/api/v1/inspections/{created['id']}/assign",
        headers=admin_headers,
        json={"inspectorId": str(identities["profile_b"].id)},
    )
    assert cross_org.status_code == 404

    unauthorized = client.post(
        f"/api/v1/inspections/{created['id']}/assign",
        headers=inspector_headers,
        json={"inspectorId": str(identities["profile_a"].id)},
    )
    assert unauthorized.status_code == 403


def test_inactive_inspector_assignment_rejected(client, db):
    identities = seed_identity_set(db)
    identities["profile_a"].active = False
    db.commit()
    headers = login(client, identities["admin_a"])
    created = create_inspection(client, headers)
    response = client.post(
        f"/api/v1/inspections/{created['id']}/assign",
        headers=headers,
        json={"inspectorId": str(identities["profile_a"].id)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSPECTOR_INACTIVE"


def test_reassignment_preserves_history_and_resets_status(client, db):
    identities = seed_identity_set(db)
    headers = login(client, identities["admin_a"])
    created = create_inspection(client, headers)
    client.post(
        f"/api/v1/inspections/{created['id']}/assign",
        headers=headers,
        json={"inspectorId": str(identities["profile_a"].id)},
    )
    response = client.post(
        f"/api/v1/inspections/{created['id']}/reassign",
        headers=headers,
        json={
            "inspectorId": str(identities["profile_a2"].id),
            "reason": "Original inspector unavailable",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ASSIGNED"
    detail = client.get(f"/api/v1/inspections/{created['id']}", headers=headers).json()
    assert len(detail["assignmentHistory"]) == 2
    statuses = {item["status"] for item in detail["assignmentHistory"]}
    assert statuses == {"ACTIVE", "REASSIGNED"}
    assert db.query(InspectionAssignment).count() == 2


def test_invalid_status_transition_and_cancellation(client, db):
    identities = seed_identity_set(db)
    admin_headers = login(client, identities["admin_a"])
    inspector_headers = login(client, identities["inspector_a"])
    created = create_inspection(client, admin_headers)
    client.post(
        f"/api/v1/inspections/{created['id']}/assign",
        headers=admin_headers,
        json={"inspectorId": str(identities["profile_a"].id)},
    )

    too_soon = client.post(f"/api/v1/inspections/{created['id']}/ready", headers=inspector_headers)
    assert too_soon.status_code == 409

    cancelled = client.post(
        f"/api/v1/inspections/{created['id']}/cancel",
        headers=admin_headers,
        json={"reason": "Verification no longer required"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    reassign = client.post(
        f"/api/v1/inspections/{created['id']}/reassign",
        headers=admin_headers,
        json={"inspectorId": str(identities["profile_a2"].id), "reason": "Try after cancel"},
    )
    assert reassign.status_code == 409


def test_pagination_filters_and_summary_use_real_records(client, db):
    identities = seed_identity_set(db)
    headers = login(client, identities["admin_a"])
    for index in range(3):
        create_inspection(client, headers, title=f"Road inspection {index}")

    page = client.get("/api/v1/inspections?page=1&pageSize=2&search=Road", headers=headers)
    assert page.status_code == 200
    body = page.json()
    assert body["totalItems"] == 3
    assert body["totalPages"] == 2
    assert len(body["items"]) == 2

    summary = client.get("/api/v1/inspections/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["total"] == 3
    assert summary.json()["draft"] == 3


def test_admin_can_create_and_list_inspector(client, db):
    identities = seed_identity_set(db)
    headers = login(client, identities["admin_a"])
    email = f"new-{uuid.uuid4()}@example.com"
    response = client.post(
        "/api/v1/inspectors",
        headers=headers,
        json={
            "fullName": "New Inspector",
            "email": email,
            "password": PASSWORD,
            "employeeCode": f"NEW-{uuid.uuid4().hex[:6]}",
        },
    )
    assert response.status_code == 201, response.text
    listing = client.get("/api/v1/inspectors?active=true&search=New", headers=headers)
    assert listing.status_code == 200
    assert any(item["email"] == email for item in listing.json()["items"])


def test_admin_can_edit_inspection_requirements(client, db):
    identities = seed_identity_set(db)
    headers = login(client, identities["admin_a"])
    created = create_inspection(client, headers)

    updated = client.patch(
        f"/api/v1/inspections/{created['id']}",
        headers=headers,
        json={
            "title": "Verify repaired pothole and markings",
            "allowedRadiusMeters": 125,
            "priority": "CRITICAL",
        },
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Verify repaired pothole and markings"
    assert updated.json()["allowedRadiusMeters"] == 125
    assert updated.json()["priority"] == "CRITICAL"
    assert db.query(AuditLog).filter(AuditLog.action == "INSPECTION_UPDATED").count() == 1


def test_cancelled_draft_cannot_be_assigned(client, db):
    identities = seed_identity_set(db)
    headers = login(client, identities["admin_a"])
    created = create_inspection(client, headers)
    cancelled = client.post(
        f"/api/v1/inspections/{created['id']}/cancel",
        headers=headers,
        json={"reason": "Work order withdrawn"},
    )
    assert cancelled.status_code == 200

    response = client.post(
        f"/api/v1/inspections/{created['id']}/assign",
        headers=headers,
        json={"inspectorId": str(identities["profile_a"].id)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSPECTION_NOT_ASSIGNABLE"
