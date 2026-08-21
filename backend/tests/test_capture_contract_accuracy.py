import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Inspection, VerificationSession
from tests.phase3_helpers import (
    create_ready_inspection,
    create_session,
    finish_capture,
    login,
    seed_identities,
    start_capture,
)
from tests.phase4_helpers import complete_required_challenges


@pytest.mark.parametrize("seconds", [10, 30, 45, 46, 59, 60, 74, 75])
def test_capture_duration_configuration_accepts_supported_boundaries(client, db, seconds):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    created = client.post(
        "/api/v1/inspections",
        headers=admin_headers,
        json={
            "title": f"Duration {seconds}",
            "inspectionType": "GENERAL",
            "location": {"latitude": 22.5726, "longitude": 88.3639},
            "allowedRadiusMeters": 100,
            "captureDurationSeconds": seconds,
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "priority": "MEDIUM",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["captureDurationSeconds"] == seconds


@pytest.mark.parametrize("seconds", [9, 76, 89, 90])
def test_capture_duration_configuration_rejects_out_of_contract_values(client, db, seconds):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    response = client.post(
        "/api/v1/inspections",
        headers=admin_headers,
        json={
            "title": f"Invalid duration {seconds}",
            "inspectionType": "GENERAL",
            "location": {"latitude": 22.5726, "longitude": 88.3639},
            "allowedRadiusMeters": 100,
            "captureDurationSeconds": seconds,
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "priority": "MEDIUM",
        },
    )
    assert response.status_code == 422


def test_session_response_is_authoritative_after_admin_edit_race(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])

    inspection_id = create_ready_inspection(
        client,
        admin_headers,
        inspector_headers,
        identities["profile"].id,
        capture_duration_seconds=30,
    )
    stale_android_copy = client.get(
        f"/api/v1/inspections/{inspection_id}",
        headers=inspector_headers,
    ).json()
    assert stale_android_copy["captureDurationSeconds"] == 30

    updated = client.patch(
        f"/api/v1/inspections/{inspection_id}",
        headers=admin_headers,
        json={"captureDurationSeconds": 60},
    )
    assert updated.status_code == 200, updated.text

    created = create_session(client, inspector_headers, inspection_id)
    assert created.status_code == 201, created.text
    contract = created.json()
    assert contract["requiredCaptureDurationSeconds"] == 60
    assert contract["captureMaximumSeconds"] == 75
    assert contract["allowedRadiusMeters"] == 100
    assert contract["deadline"]


def test_session_snapshot_remains_stable_if_inspection_row_changes(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client,
        admin_headers,
        inspector_headers,
        identities["profile"].id,
        capture_duration_seconds=60,
    )
    created = create_session(client, inspector_headers, inspection_id)
    assert created.status_code == 201, created.text
    session_id = created.json()["sessionId"]

    # Simulate a later row mutation without touching the immutable session snapshot.
    inspection = db.get(Inspection, uuid.UUID(inspection_id))
    inspection.capture_duration_seconds = 30
    db.commit()

    session = db.get(VerificationSession, uuid.UUID(session_id))
    assert session.site_snapshot["captureDurationSeconds"] == 60
    assert start_capture(client, inspector_headers, session_id).status_code == 200
    complete_required_challenges(client, inspector_headers, session_id)

    too_short = client.post(
        f"/api/v1/sessions/{session_id}/capture-complete",
        headers=inspector_headers,
        json=_capture_complete_payload(59_999),
    )
    assert too_short.status_code == 422
    assert too_short.json()["error"]["code"] == "CAPTURE_TOO_SHORT"

    exact = client.post(
        f"/api/v1/sessions/{session_id}/capture-complete",
        headers=inspector_headers,
        json=_capture_complete_payload(60_000),
    )
    assert exact.status_code == 200, exact.text
    assert exact.json()["captureDurationMs"] == 60_000


def test_75_second_capture_accepts_exact_minimum_and_rejects_over_90_seconds(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])

    inspection_id = create_ready_inspection(
        client,
        admin_headers,
        inspector_headers,
        identities["profile"].id,
        capture_duration_seconds=75,
    )
    session = create_session(client, inspector_headers, inspection_id)
    assert session.status_code == 201, session.text
    assert session.json()["requiredCaptureDurationSeconds"] == 75
    assert session.json()["captureMaximumSeconds"] == 90
    session_id = session.json()["sessionId"]
    assert start_capture(client, inspector_headers, session_id).status_code == 200
    complete_required_challenges(client, inspector_headers, session_id)

    too_long = client.post(
        f"/api/v1/sessions/{session_id}/capture-complete",
        headers=inspector_headers,
        json=_capture_complete_payload(90_001),
    )
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "CAPTURE_TOO_LONG"

    exact = client.post(
        f"/api/v1/sessions/{session_id}/capture-complete",
        headers=inspector_headers,
        json=_capture_complete_payload(75_000),
    )
    assert exact.status_code == 200, exact.text


def test_large_gps_uncertainty_inside_radius_is_inconclusive(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client,
        admin_headers,
        inspector_headers,
        identities["profile"].id,
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]

    response = start_capture(
        client,
        inspector_headers,
        session_id,
        latitude=22.5726,
        longitude=88.3639,
        accuracyMeters=900.0,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LOCATION_INCONCLUSIVE"


def _capture_complete_payload(duration_ms: int) -> dict:
    return {
        "captureDurationMs": duration_ms,
        "videoFileCount": 1,
        "sensorSummary": {
            "accelerometerSamples": 3,
            "gyroscopeSamples": 2,
            "rotationVectorSamples": 2,
            "magnetometerSamples": 0,
        },
        "locationSummary": {
            "locationSamples": 2,
            "bestAccuracyMeters": 7.5,
            "firstRelativeTimestampNs": 1_000_000_000,
            "lastRelativeTimestampNs": 2_000_000_000,
        },
    }
