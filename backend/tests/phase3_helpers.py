import gzip
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.models import Inspector, Organization, User, UserRole
from tests.phase4_helpers import complete_required_challenges

PASSWORD = "SiteProofTest!42"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seed_identities(db):
    org = Organization(name=f"Phase 3 Authority {uuid.uuid4()}")
    other_org = Organization(name=f"Other Authority {uuid.uuid4()}")
    db.add_all([org, other_org])
    db.flush()

    def user(email_prefix, name, role, organization):
        account = User(
            organization_id=organization.id,
            email=f"{email_prefix}-{uuid.uuid4()}@example.com",
            full_name=name,
            hashed_password=hash_password(PASSWORD),
            role=role,
            is_active=True,
        )
        db.add(account)
        db.flush()
        profile = None
        if role == UserRole.INSPECTOR:
            profile = Inspector(
                organization_id=organization.id,
                user_id=account.id,
                employee_code=f"EMP-{str(account.id)[:8]}",
                active=True,
            )
            db.add(profile)
            db.flush()
        return account, profile

    admin, _ = user("admin", "Admin", UserRole.ADMIN, org)
    inspector, profile = user("inspector", "Inspector", UserRole.INSPECTOR, org)
    inspector2, profile2 = user("inspector2", "Inspector 2", UserRole.INSPECTOR, org)
    other_admin, _ = user("other-admin", "Other Admin", UserRole.ADMIN, other_org)
    db.commit()
    return {
        "org": org,
        "admin": admin,
        "inspector": inspector,
        "profile": profile,
        "inspector2": inspector2,
        "profile2": profile2,
        "other_admin": other_admin,
    }


def login(client, user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def create_ready_inspection(
    client,
    admin_headers,
    inspector_headers,
    profile_id,
    *,
    capture_duration_seconds: int = 10,
):
    payload = {
        "title": "Verify repaired road section",
        "description": "Phase 3 live capture test",
        "inspectionType": "ROAD_REPAIR",
        "location": {
            "latitude": 22.5726,
            "longitude": 88.3639,
            "name": "Central Avenue",
        },
        "allowedRadiusMeters": 100,
        "captureDurationSeconds": capture_duration_seconds,
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "priority": "HIGH",
        "instructions": "Record the repaired road surface.",
    }
    created = client.post("/api/v1/inspections", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    inspection_id = created.json()["id"]
    assigned = client.post(
        f"/api/v1/inspections/{inspection_id}/assign",
        headers=admin_headers,
        json={"inspectorId": str(profile_id)},
    )
    assert assigned.status_code == 200, assigned.text
    acknowledged = client.post(
        f"/api/v1/inspections/{inspection_id}/acknowledge",
        headers=inspector_headers,
    )
    assert acknowledged.status_code == 200, acknowledged.text
    ready = client.post(
        f"/api/v1/inspections/{inspection_id}/ready",
        headers=inspector_headers,
    )
    assert ready.status_code == 200, ready.text
    return inspection_id


def create_session(client, inspector_headers, inspection_id, device_session_id=None):
    return client.post(
        f"/api/v1/inspections/{inspection_id}/sessions",
        headers=inspector_headers,
        json={
            "deviceSessionId": device_session_id or str(uuid.uuid4()),
            "clientTime": datetime.now(timezone.utc).isoformat(),
            "clientMonotonicNs": 123456789,
            "clientVersion": "0.4.0-test",
            "androidVersion": "15",
            "deviceModel": "Test device",
        },
    )


def start_capture(client, headers, session_id, **location_overrides):
    location = {
        "latitude": 22.5726,
        "longitude": 88.3639,
        "accuracyMeters": 8.0,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "elapsedRealtimeNs": 555000000,
    }
    location.update(location_overrides)
    return client.post(
        f"/api/v1/sessions/{session_id}/start-capture",
        headers=headers,
        json={
            "clientWallClock": datetime.now(timezone.utc).isoformat(),
            "clientMonotonicNs": 600000000,
            "location": location,
            "capabilities": {
                "accelerometer": True,
                "gyroscope": True,
                "rotationVector": True,
                "magnetometer": False,
            },
        },
    )


def finish_capture(client, headers, session_id, capture_duration_ms: int = 10_000):
    complete_required_challenges(client, headers, session_id)
    return client.post(
        f"/api/v1/sessions/{session_id}/capture-complete",
        headers=headers,
        json={
            "captureDurationMs": capture_duration_ms,
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
        },
    )


def build_evidence(session_id, capture_duration_ms: int = 10_000):
    video = b"\x00\x00\x00\x18ftypmp42siteproof-phase3-test"
    sensor_lines = [
        {"type": "ACCELEROMETER", "relativeTimestampNs": 100, "values": [0.1, 9.7, 0.2], "accuracy": 3},
        {"type": "GYROSCOPE", "relativeTimestampNs": 200, "values": [0.01, 0.02, 0.03], "accuracy": 3},
        {"type": "ROTATION_VECTOR", "relativeTimestampNs": 300, "values": [0.1, 0.2, 0.3, 0.9], "accuracy": 3},
        {"type": "ACCELEROMETER", "relativeTimestampNs": 400, "values": [0.2, 9.6, 0.3], "accuracy": 3},
        {"type": "GYROSCOPE", "relativeTimestampNs": 500, "values": [0.02, 0.03, 0.04], "accuracy": 3},
        {"type": "ROTATION_VECTOR", "relativeTimestampNs": 600, "values": [0.2, 0.3, 0.4, 0.8], "accuracy": 3},
        {"type": "ACCELEROMETER", "relativeTimestampNs": 700, "values": [0.3, 9.5, 0.4], "accuracy": 3},
    ]
    sensors = gzip.compress(
        ("\n".join(json.dumps(row, separators=(",", ":")) for row in sensor_lines) + "\n").encode()
    )
    locations_doc = [
        {"relativeTimestampNs": 1_000_000_000, "latitude": 22.5726, "longitude": 88.3639, "accuracyMeters": 8.0},
        {"relativeTimestampNs": 2_000_000_000, "latitude": 22.57261, "longitude": 88.36391, "accuracyMeters": 7.5},
    ]
    locations = gzip.compress(json.dumps(locations_doc, separators=(",", ":")).encode())
    metadata = json.dumps(
        {
            "sessionId": session_id,
            "inspectionId": "test",
            "capture": {"durationMs": capture_duration_ms},
            "device": {"model": "Test device"},
        },
        separators=(",", ":"),
    ).encode()
    files = {
        "VIDEO": ("capture.mp4", "video/mp4", video),
        "SENSOR_DATA": ("sensors.ndjson.gz", "application/octet-stream", sensors),
        "LOCATION_DATA": ("locations.json.gz", "application/gzip", locations),
        "SESSION_METADATA": ("metadata.json", "application/json", metadata),
    }
    manifest = {
        "sessionId": session_id,
        "files": [
            {"type": file_type, "name": filename, "sizeBytes": len(content), "sha256": sha256(content)}
            for file_type, (filename, _, content) in files.items()
        ],
    }
    manifest_bytes = json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode()
    files["MANIFEST"] = ("manifest.json", "application/json", manifest_bytes)
    return files


def upload_all_evidence(client, headers, session_id, files):
    descriptors = [
        {
            "type": file_type,
            "filename": filename,
            "mimeType": mime,
            "sizeBytes": len(content),
            "sha256": sha256(content),
        }
        for file_type, (filename, mime, content) in files.items()
    ]
    initiated = client.post(
        f"/api/v1/sessions/{session_id}/evidence/initiate",
        headers=headers,
        json={"idempotencyKey": f"batch-{uuid.uuid4()}", "files": descriptors},
    )
    assert initiated.status_code == 200, initiated.text
    targets = {target["type"]: target for target in initiated.json()["targets"]}
    for file_type, (_, mime, content) in files.items():
        target = targets[file_type]
        response = client.put(
            f"/api/v1/{target['uploadPath']}",
            headers={**headers, "Content-Type": mime},
            content=content,
        )
        assert response.status_code == 200, response.text
        assert response.json()["hashVerified"] is True
    return client.post(
        f"/api/v1/sessions/{session_id}/evidence/complete",
        headers=headers,
        json={"manifestSha256": sha256(files["MANIFEST"][2])},
    )
