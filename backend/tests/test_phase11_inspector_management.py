import uuid

from app.core.security import hash_password
from app.models import Inspector, Organization, User, UserRole

ADMIN_PASSWORD = "AdminPassword!42"
INSPECTOR_PASSWORD = "InspectorPassword!42"
NEW_PASSWORD = "InspectorPassword!99"


def seed_users(db):
    org = Organization(name=f"Inspector Management {uuid.uuid4()}")
    db.add(org)
    db.flush()

    admin = User(
        organization_id=org.id,
        email=f"admin-{uuid.uuid4()}@example.com",
        full_name="Admin User",
        hashed_password=hash_password(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
    )
    inspector_user = User(
        organization_id=org.id,
        email=f"inspector-{uuid.uuid4()}@example.com",
        full_name="Inspector User",
        hashed_password=hash_password(INSPECTOR_PASSWORD),
        role=UserRole.INSPECTOR,
        is_active=True,
    )
    db.add_all([admin, inspector_user])
    db.flush()

    inspector = Inspector(
        organization_id=org.id,
        user_id=inspector_user.id,
        employee_code="INSP-1001",
        active=True,
    )
    db.add(inspector)
    db.commit()
    return admin, inspector_user, inspector


def login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def auth_headers(client, user, password):
    response = login(client, user.email, password)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_admin_can_reset_password_and_change_inspector_status(client, db):
    admin, inspector_user, inspector = seed_users(db)
    headers = auth_headers(client, admin, ADMIN_PASSWORD)

    reset = client.put(
        f"/api/v1/inspectors/{inspector.id}/password",
        headers=headers,
        json={"password": NEW_PASSWORD},
    )
    assert reset.status_code == 204, reset.text
    assert login(client, inspector_user.email, INSPECTOR_PASSWORD).status_code == 401
    assert login(client, inspector_user.email, NEW_PASSWORD).status_code == 200

    deactivate = client.patch(
        f"/api/v1/inspectors/{inspector.id}",
        headers=headers,
        json={"active": False},
    )
    assert deactivate.status_code == 200, deactivate.text
    assert deactivate.json()["active"] is False
    assert login(client, inspector_user.email, NEW_PASSWORD).status_code == 401

    all_accounts = client.get("/api/v1/inspectors", headers=headers)
    assert all_accounts.status_code == 200
    assert any(item["id"] == str(inspector.id) for item in all_accounts.json()["items"])


def test_inspector_cannot_manage_other_inspector_accounts(client, db):
    admin, inspector_user, inspector = seed_users(db)
    inspector_headers = auth_headers(client, inspector_user, INSPECTOR_PASSWORD)

    reset = client.put(
        f"/api/v1/inspectors/{inspector.id}/password",
        headers=inspector_headers,
        json={"password": NEW_PASSWORD},
    )
    assert reset.status_code == 403

    update = client.patch(
        f"/api/v1/inspectors/{inspector.id}",
        headers=inspector_headers,
        json={"active": False},
    )
    assert update.status_code == 403
