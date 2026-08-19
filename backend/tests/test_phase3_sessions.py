import uuid
from datetime import datetime, timedelta, timezone

from app.models import VerificationSession
from app.models.verification import VerificationSessionStatus
from tests.phase3_helpers import (
    create_ready_inspection,
    create_session,
    finish_capture,
    login,
    seed_identities,
    start_capture,
)


def test_session_creation_requires_ready_active_assignee(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    wrong_headers = login(client, identities["inspector2"])
    inspection_id = create_ready_inspection(
        client, admin_headers, inspector_headers, identities["profile"].id
    )
    wrong = create_session(client, wrong_headers, inspection_id)
    assert wrong.status_code == 403

    created = create_session(client, inspector_headers, inspection_id)
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "CREATED"
    assert created.json()["serverTime"]
    assert created.json()["clockOffsetMs"] is not None

    duplicate = create_session(client, inspector_headers, inspection_id)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ACTIVE_SESSION_EXISTS"


def test_non_ready_and_admin_cannot_create_session(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    payload = {
        "title": "Not ready",
        "inspectionType": "GENERAL",
        "location": {"latitude": 22.5726, "longitude": 88.3639},
        "allowedRadiusMeters": 100,
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "priority": "MEDIUM",
    }
    created = client.post("/api/v1/inspections", headers=admin_headers, json=payload).json()
    admin_attempt = create_session(client, admin_headers, created["id"])
    assert admin_attempt.status_code == 403

    client.post(
        f"/api/v1/inspections/{created['id']}/assign",
        headers=admin_headers,
        json={"inspectorId": str(identities["profile"].id)},
    )
    not_ready = create_session(client, inspector_headers, created["id"])
    assert not_ready.status_code == 409
    assert not_ready.json()["error"]["code"] == "INSPECTION_NOT_READY"


def test_location_boundary_and_capture_state_transitions(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client, admin_headers, inspector_headers, identities["profile"].id
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]

    invalid_complete = finish_capture(client, inspector_headers, session_id)
    assert invalid_complete.status_code == 409

    outside = start_capture(
        client,
        inspector_headers,
        session_id,
        latitude=22.5790,
        longitude=88.3639,
        accuracyMeters=10.0,
    )
    assert outside.status_code == 409
    assert outside.json()["error"]["code"] == "OUTSIDE_ALLOWED_LOCATION"

    started = start_capture(client, inspector_headers, session_id)
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "CAPTURING"

    completed = finish_capture(client, inspector_headers, session_id)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "CAPTURE_COMPLETED"


def test_capture_completion_is_idempotent_for_worker_retry(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client, admin_headers, inspector_headers, identities["profile"].id
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]
    assert start_capture(client, inspector_headers, session_id).status_code == 200

    first = finish_capture(client, inspector_headers, session_id)
    second = finish_capture(client, inspector_headers, session_id)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "CAPTURE_COMPLETED"
    assert second.json()["captureDurationMs"] == first.json()["captureDurationMs"]


def test_delayed_capture_completion_survives_offline_gap_if_capture_finished_in_time(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client, admin_headers, inspector_headers, identities["profile"].id
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]
    assert start_capture(client, inspector_headers, session_id).status_code == 200

    row = db.get(VerificationSession, uuid.UUID(session_id))
    simulated_start = datetime.now(timezone.utc) - timedelta(minutes=30)
    row.capture_started_at = simulated_start
    row.expires_at = simulated_start + timedelta(minutes=15)
    db.commit()

    delayed = finish_capture(client, inspector_headers, session_id)
    assert delayed.status_code == 200, delayed.text
    assert delayed.json()["status"] == "CAPTURE_COMPLETED"
    db.refresh(row)
    assert row.status == VerificationSessionStatus.CAPTURE_COMPLETED


def test_session_expiration_and_abort_are_terminal(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client, admin_headers, inspector_headers, identities["profile"].id
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]
    row = db.get(VerificationSession, uuid.UUID(session_id))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    expired = start_capture(client, inspector_headers, session_id)
    assert expired.status_code == 409
    assert expired.json()["error"]["code"] == "SESSION_EXPIRED"
    db.refresh(row)
    assert row.status == VerificationSessionStatus.EXPIRED

    second = create_session(client, inspector_headers, inspection_id)
    assert second.status_code == 201, second.text
    second_id = second.json()["sessionId"]
    aborted = client.post(
        f"/api/v1/sessions/{second_id}/abort",
        headers=inspector_headers,
        json={"reason": "USER_CANCELLED"},
    )
    assert aborted.status_code == 200
    assert aborted.json()["status"] == "ABORTED"
    cannot_restart = start_capture(client, inspector_headers, second_id)
    assert cannot_restart.status_code == 409
