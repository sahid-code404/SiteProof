import uuid

from app.core.config import Settings
from app.models.challenge import ChallengeResult, ChallengeType, VerificationChallenge
from app.schemas.challenge import ChallengeSubmitRequest
from app.services.challenges.validators.rotate import RotateChallengeValidator
from tests.phase3_helpers import create_ready_inspection, create_session, login, seed_identities, start_capture
from tests.phase4_helpers import CAPTURE_ANCHOR_NS, synthetic_sensor_body


def test_small_rotation_is_a_clear_failure():
    challenge = VerificationChallenge(
        challenge_type=ChallengeType.ROTATE_RIGHT,
        parameters_json={"targetDegrees": 40.0, "minDegrees": 28.0, "maxDegrees": 54.0},
    )
    wire = {
        "challengeId": str(uuid.uuid4()),
        "type": "ROTATE_RIGHT",
        "nonce": "synthetic-nonce-with-enough-entropy",
        "parameters": challenge.parameters_json,
    }
    payload = ChallengeSubmitRequest.model_validate(
        synthetic_sensor_body(wire, magnitude_factor=0.25)
    )
    result = RotateChallengeValidator().validate(
        challenge,
        payload,
        capabilities={"gyroscope": True, "rotation_vector": True},
        settings=Settings(),
    )
    assert result.result == ChallengeResult.FAIL
    assert result.failure_reason == "INSUFFICIENT_MOVEMENT"


def test_admin_and_cross_organization_user_cannot_perform_inspector_challenge(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    other_admin_headers = login(client, identities["other_admin"])
    inspection_id = create_ready_inspection(
        client,
        admin_headers,
        inspector_headers,
        identities["profile"].id,
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]
    assert start_capture(client, inspector_headers, session_id).status_code == 200
    issued_response = client.post(
        f"/api/v1/sessions/{session_id}/challenges/next",
        headers=inspector_headers,
    )
    assert issued_response.status_code == 200, issued_response.text
    issued = issued_response.json()
    payload = {
        "nonce": issued["nonce"],
        "clientMonotonicNs": CAPTURE_ANCHOR_NS + 500_000_000,
    }

    admin_attempt = client.post(
        f"/api/v1/challenges/{issued['challengeId']}/start",
        headers=admin_headers,
        json=payload,
    )
    assert admin_attempt.status_code == 403

    cross_org_attempt = client.post(
        f"/api/v1/challenges/{issued['challengeId']}/start",
        headers=other_admin_headers,
        json=payload,
    )
    assert cross_org_attempt.status_code in {403, 404}
