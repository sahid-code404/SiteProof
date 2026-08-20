import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import Settings
from app.models import VerificationChallenge
from app.models.challenge import ChallengeResult, ChallengeStatus, ChallengeType
from app.schemas.challenge import ChallengeSubmitRequest
from app.services.challenges.validators.rotate import RotateChallengeValidator
from app.services.challenges.validators.tilt import TiltChallengeValidator
from tests.phase3_helpers import create_ready_inspection, create_session, login, seed_identities, start_capture
from tests.phase4_helpers import (
    CAPTURE_ANCHOR_NS,
    complete_required_challenges,
    perform_current_challenge,
    synthetic_sensor_body,
)


def _challenge(challenge_type: ChallengeType, target: float = 40.0) -> VerificationChallenge:
    return VerificationChallenge(
        challenge_type=challenge_type,
        parameters_json={
            "targetDegrees": target,
            "minDegrees": max(15.0, target - 12.0),
            "maxDegrees": target + 14.0,
        },
    )


@pytest.mark.parametrize(
    ("challenge_type", "validator"),
    [
        (ChallengeType.ROTATE_RIGHT, RotateChallengeValidator()),
        (ChallengeType.ROTATE_LEFT, RotateChallengeValidator()),
        (ChallengeType.TILT_UP, TiltChallengeValidator()),
        (ChallengeType.TILT_DOWN, TiltChallengeValidator()),
    ],
)
def test_valid_synthetic_motion_passes(challenge_type, validator):
    challenge = _challenge(challenge_type)
    wire = {
        "challengeId": str(uuid.uuid4()),
        "type": challenge_type.value,
        "nonce": "synthetic-nonce-with-enough-entropy",
        "parameters": challenge.parameters_json,
    }
    payload = ChallengeSubmitRequest.model_validate(synthetic_sensor_body(wire))
    result = validator.validate(
        challenge,
        payload,
        capabilities={"gyroscope": True, "rotation_vector": True},
        settings=Settings(),
    )
    assert result.result == ChallengeResult.PASS
    assert result.score >= 0.75
    assert result.metrics["observedGyroDegrees"] > 25


def test_wrong_direction_fails():
    challenge = _challenge(ChallengeType.ROTATE_RIGHT)
    wire = {
        "challengeId": str(uuid.uuid4()),
        "type": "ROTATE_RIGHT",
        "nonce": "synthetic-nonce-with-enough-entropy",
        "parameters": challenge.parameters_json,
    }
    payload = ChallengeSubmitRequest.model_validate(
        synthetic_sensor_body(wire, wrong_direction=True)
    )
    result = RotateChallengeValidator().validate(
        challenge,
        payload,
        capabilities={"gyroscope": True, "rotation_vector": True},
        settings=Settings(),
    )
    assert result.result == ChallengeResult.FAIL
    assert result.failure_reason == "WRONG_DIRECTION"


def test_sensor_conflict_is_inconclusive():
    challenge = _challenge(ChallengeType.TILT_DOWN)
    wire = {
        "challengeId": str(uuid.uuid4()),
        "type": "TILT_DOWN",
        "nonce": "synthetic-nonce-with-enough-entropy",
        "parameters": challenge.parameters_json,
    }
    payload = ChallengeSubmitRequest.model_validate(
        synthetic_sensor_body(wire, rotation_vector_conflict=True)
    )
    result = TiltChallengeValidator().validate(
        challenge,
        payload,
        capabilities={"gyroscope": True, "rotation_vector": True},
        settings=Settings(),
    )
    assert result.result == ChallengeResult.INCONCLUSIVE
    assert result.failure_reason == "SENSOR_CONFLICT"


def test_missing_gyro_is_inconclusive():
    challenge = _challenge(ChallengeType.ROTATE_LEFT)
    wire = {
        "challengeId": str(uuid.uuid4()),
        "type": "ROTATE_LEFT",
        "nonce": "synthetic-nonce-with-enough-entropy",
        "parameters": challenge.parameters_json,
    }
    body = synthetic_sensor_body(wire)
    body["samples"] = [sample for sample in body["samples"] if sample["type"] != "GYROSCOPE"]
    payload = ChallengeSubmitRequest.model_validate(body)
    result = RotateChallengeValidator().validate(
        challenge,
        payload,
        capabilities={"gyroscope": True, "rotation_vector": True},
        settings=Settings(),
    )
    assert result.result == ChallengeResult.INCONCLUSIVE
    assert result.failure_reason == "GYROSCOPE_UNAVAILABLE"


def _started_session(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client, admin_headers, inspector_headers, identities["profile"].id
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]
    started = start_capture(client, inspector_headers, session_id)
    assert started.status_code == 200, started.text
    return identities, admin_headers, inspector_headers, inspection_id, session_id


def test_next_is_idempotent_and_does_not_preload_future_challenges(client, db):
    _, _, headers, _, session_id = _started_session(client, db)
    first = client.post(f"/api/v1/sessions/{session_id}/challenges/next", headers=headers)
    repeated = client.post(f"/api/v1/sessions/{session_id}/challenges/next", headers=headers)
    assert first.status_code == repeated.status_code == 200
    assert repeated.json()["challengeId"] == first.json()["challengeId"]
    assert repeated.json()["nonce"] == first.json()["nonce"]
    assert db.query(VerificationChallenge).filter_by(session_id=uuid.UUID(session_id)).count() == 1


def test_nonce_and_authorization_are_enforced(client, db):
    identities, _, headers, _, session_id = _started_session(client, db)
    other_headers = login(client, identities["inspector2"])
    issued = client.post(f"/api/v1/sessions/{session_id}/challenges/next", headers=headers).json()

    wrong_owner = client.post(
        f"/api/v1/challenges/{issued['challengeId']}/start",
        headers=other_headers,
        json={"nonce": issued["nonce"], "clientMonotonicNs": CAPTURE_ANCHOR_NS + 500_000_000},
    )
    assert wrong_owner.status_code in {403, 404}

    wrong_nonce = client.post(
        f"/api/v1/challenges/{issued['challengeId']}/start",
        headers=headers,
        json={"nonce": "wrong-nonce-value-that-is-long", "clientMonotonicNs": CAPTURE_ANCHOR_NS + 500_000_000},
    )
    assert wrong_nonce.status_code == 409
    assert wrong_nonce.json()["error"]["code"] == "CHALLENGE_NONCE_INVALID"


def test_submission_is_idempotent_but_replay_with_different_payload_is_rejected(client, db):
    _, _, headers, _, session_id = _started_session(client, db)
    challenge, body, submitted = perform_current_challenge(
        client, headers, session_id, start_relative_ns=500_000_000
    )
    assert submitted.status_code == 200, submitted.text

    duplicate = client.post(
        f"/api/v1/challenges/{challenge['challengeId']}/submit",
        headers=headers,
        json=body,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["result"] == submitted.json()["result"]

    changed = dict(body)
    changed["idempotencyKey"] = f"different-{uuid.uuid4()}"
    replay = client.post(
        f"/api/v1/challenges/{challenge['challengeId']}/submit",
        headers=headers,
        json=changed,
    )
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "CHALLENGE_ALREADY_COMPLETED"


def test_reversed_timestamps_are_rejected(client, db):
    _, _, headers, _, session_id = _started_session(client, db)
    issued = client.post(f"/api/v1/sessions/{session_id}/challenges/next", headers=headers).json()
    start_relative = 500_000_000
    client.post(
        f"/api/v1/challenges/{issued['challengeId']}/start",
        headers=headers,
        json={"nonce": issued["nonce"], "clientMonotonicNs": CAPTURE_ANCHOR_NS + start_relative},
    )
    body = synthetic_sensor_body(issued, start_relative_ns=start_relative, reverse_timestamps=True)
    response = client.post(
        f"/api/v1/challenges/{issued['challengeId']}/submit",
        headers=headers,
        json=body,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SENSOR_EVIDENCE_INVALID"


def test_expired_physical_window_is_rejected(client, db):
    _, _, headers, _, session_id = _started_session(client, db)
    issued = client.post(f"/api/v1/sessions/{session_id}/challenges/next", headers=headers).json()
    start_relative = 500_000_000
    client.post(
        f"/api/v1/challenges/{issued['challengeId']}/start",
        headers=headers,
        json={"nonce": issued["nonce"], "clientMonotonicNs": CAPTURE_ANCHOR_NS + start_relative},
    )
    body = synthetic_sensor_body(issued, start_relative_ns=start_relative)
    shift = 16_000_000_000
    body["sensorWindow"]["endRelativeNs"] += shift
    for sample in body["samples"]:
        sample["relativeTimestampNs"] += shift
    body["sensorWindow"]["startRelativeNs"] += shift
    response = client.post(
        f"/api/v1/challenges/{issued['challengeId']}/submit",
        headers=headers,
        json=body,
    )
    assert response.status_code in {409, 422}


def test_full_three_challenge_sequence_reaches_completed_state(client, db):
    _, _, headers, _, session_id = _started_session(client, db)
    complete_required_challenges(client, headers, session_id)
    session = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    assert session.status_code == 200
    assert session.json()["status"] == "CHALLENGES_COMPLETED"
    timeline = client.get(f"/api/v1/sessions/{session_id}/challenges", headers=headers)
    assert timeline.status_code == 200
    items = timeline.json()["items"]
    assert len(items) == 3
    assert all(item["result"] == "PASS" for item in items)
    assert all(item["score"] >= 0.75 for item in items)


def test_expired_active_challenge_gets_new_nonce_on_retry(client, db):
    _, _, headers, _, session_id = _started_session(client, db)
    first = client.post(f"/api/v1/sessions/{session_id}/challenges/next", headers=headers).json()
    row = db.get(VerificationChallenge, uuid.UUID(first["challengeId"]))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    replacement = client.post(f"/api/v1/sessions/{session_id}/challenges/next", headers=headers)
    assert replacement.status_code == 200, replacement.text
    assert replacement.json()["sequenceNumber"] == first["sequenceNumber"]
    assert replacement.json()["attemptNumber"] == 2
    assert replacement.json()["challengeId"] != first["challengeId"]
    assert replacement.json()["nonce"] != first["nonce"]
    db.refresh(row)
    assert row.status == ChallengeStatus.EXPIRED
