import uuid

from tests.phase3_helpers import (
    build_evidence,
    create_ready_inspection,
    create_session,
    finish_capture,
    login,
    seed_identities,
    sha256,
    start_capture,
    upload_all_evidence,
)


def test_full_evidence_upload_and_admin_visibility(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client, admin_headers, inspector_headers, identities["profile"].id
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]
    assert start_capture(client, inspector_headers, session_id).status_code == 200
    assert finish_capture(client, inspector_headers, session_id).status_code == 200

    files = build_evidence(session_id)
    completed = upload_all_evidence(client, inspector_headers, session_id, files)
    assert completed.status_code == 200, completed.text
    body = completed.json()
    assert body["status"] == "UPLOADED"
    assert body["evidence"] == {
        "video": True,
        "sensorData": True,
        "locationData": True,
        "sessionMetadata": True,
        "manifest": True,
    }

    latest = client.get(
        f"/api/v1/inspections/{inspection_id}/sessions/latest",
        headers=admin_headers,
    )
    assert latest.status_code == 200
    assert latest.json()["status"] == "UPLOADED"

    evidence = client.get(f"/api/v1/sessions/{session_id}/evidence", headers=admin_headers)
    assert evidence.status_code == 200
    video = next(item for item in evidence.json()["items"] if item["type"] == "VIDEO")
    downloaded = client.get(
        f"/api/v1/sessions/{session_id}/evidence/{video['id']}/content",
        headers=admin_headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == files["VIDEO"][2]

    inspection = client.get(f"/api/v1/inspections/{inspection_id}", headers=admin_headers)
    assert inspection.json()["status"] == "PROCESSING"


def test_hash_mismatch_marks_upload_failed_and_retry_is_idempotent(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client, admin_headers, inspector_headers, identities["profile"].id
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]
    start_capture(client, inspector_headers, session_id)
    finish_capture(client, inspector_headers, session_id)
    files = build_evidence(session_id)

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
    key = f"retry-{uuid.uuid4()}"
    initiated = client.post(
        f"/api/v1/sessions/{session_id}/evidence/initiate",
        headers=inspector_headers,
        json={"idempotencyKey": key, "files": descriptors},
    )
    assert initiated.status_code == 200
    video_target = next(target for target in initiated.json()["targets"] if target["type"] == "VIDEO")
    original = files["VIDEO"][2]
    changed = original[:-1] + bytes([original[-1] ^ 0x01])
    failed = client.put(
        f"/api/v1/{video_target['uploadPath']}",
        headers={**inspector_headers, "Content-Type": "video/mp4"},
        content=changed,
    )
    assert failed.status_code == 422
    assert failed.json()["error"]["code"] == "HASH_MISMATCH"

    retried = client.post(
        f"/api/v1/sessions/{session_id}/evidence/initiate",
        headers=inspector_headers,
        json={"idempotencyKey": key, "files": descriptors},
    )
    assert retried.status_code == 200
    same_target = next(target for target in retried.json()["targets"] if target["type"] == "VIDEO")
    assert same_target["fileId"] == video_target["fileId"]

    uploaded = client.put(
        f"/api/v1/{same_target['uploadPath']}",
        headers={**inspector_headers, "Content-Type": "video/mp4"},
        content=original,
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["hashVerified"] is True


def test_cross_organization_cannot_view_session(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    other_headers = login(client, identities["other_admin"])
    inspection_id = create_ready_inspection(
        client, admin_headers, inspector_headers, identities["profile"].id
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]
    response = client.get(f"/api/v1/sessions/{session_id}", headers=other_headers)
    assert response.status_code == 404
