import uuid

from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.challenge import VerificationChallenge
from app.models.verification import VerificationSession
from app.models.visual_motion import (
    VisualAnalysisStatus,
    VisualDirection,
    VisualMotionResult,
    VisualQuality,
)
from app.services.visual_analysis_service import _upsert_result
from tests.phase3_helpers import create_ready_inspection, create_session, login, seed_identities, start_capture


def _create_live_session(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client,
        admin_headers,
        inspector_headers,
        identities["profile"].id,
    )
    created = create_session(client, inspector_headers, inspection_id)
    assert created.status_code == 201, created.text
    session_id = created.json()["sessionId"]
    assert start_capture(client, inspector_headers, session_id).status_code == 200
    issued = client.post(
        f"/api/v1/sessions/{session_id}/challenges/next",
        headers=inspector_headers,
    )
    assert issued.status_code == 200, issued.text
    return identities, admin_headers, inspector_headers, session_id, issued.json()


def test_visual_result_upsert_is_idempotent_per_challenge_and_version(client, db):
    _, _, _, session_id, issued = _create_live_session(client, db)
    session = db.get(VerificationSession, uuid.UUID(session_id))
    challenge = db.get(VerificationChallenge, uuid.UUID(issued["challengeId"]))
    assert session is not None
    assert challenge is not None
    analysis_version = get_settings().vision_analysis_version

    _upsert_result(
        db,
        session=session,
        challenge=challenge,
        status=VisualAnalysisStatus.SUCCESS,
        direction=VisualDirection.RIGHT,
        quality=VisualQuality.GOOD,
        estimated_rotation_degrees=31.0,
        visual_confidence=0.81,
        diagnostics={"reasons": ["first pass"]},
    )
    db.commit()

    _upsert_result(
        db,
        session=session,
        challenge=challenge,
        status=VisualAnalysisStatus.SUCCESS,
        direction=VisualDirection.RIGHT,
        quality=VisualQuality.GOOD,
        estimated_rotation_degrees=32.5,
        visual_confidence=0.89,
        diagnostics={"reasons": ["same version reprocessed"]},
    )
    db.commit()

    count = db.scalar(
        select(func.count(VisualMotionResult.id)).where(
            VisualMotionResult.challenge_id == challenge.id,
            VisualMotionResult.analysis_version == analysis_version,
        )
    )
    assert count == 1
    row = db.scalar(
        select(VisualMotionResult).where(
            VisualMotionResult.challenge_id == challenge.id,
            VisualMotionResult.analysis_version == analysis_version,
        )
    )
    assert row is not None
    assert row.estimated_rotation_degrees == 32.5
    assert row.visual_confidence == 0.89
    assert row.diagnostics_json["reasons"] == ["same version reprocessed"]


def test_visual_analysis_endpoint_is_reviewer_scoped_and_does_not_fuse_sensor_result(client, db):
    identities, admin_headers, inspector_headers, session_id, issued = _create_live_session(client, db)
    session = db.get(VerificationSession, uuid.UUID(session_id))
    challenge = db.get(VerificationChallenge, uuid.UUID(issued["challengeId"]))
    assert session is not None
    assert challenge is not None

    _upsert_result(
        db,
        session=session,
        challenge=challenge,
        status=VisualAnalysisStatus.INCONCLUSIVE,
        direction=VisualDirection.NONE,
        quality=VisualQuality.POOR,
        feature_count=17,
        tracked_feature_count=12,
        visual_confidence=0.21,
        diagnostics={"reasons": ["Insufficient stable visual features."]},
    )
    db.commit()

    admin = client.get(
        f"/api/v1/sessions/{session_id}/visual-analysis",
        headers=admin_headers,
    )
    assert admin.status_code == 200, admin.text
    body = admin.json()
    assert body["status"] == "INCONCLUSIVE"
    assert body["analysisVersion"] == get_settings().vision_analysis_version
    assert len(body["challenges"]) == 1
    visual = body["challenges"][0]
    assert visual["challengeId"] == issued["challengeId"]
    assert visual["status"] == "INCONCLUSIVE"
    assert visual["visualDirection"] == "NONE"
    assert visual["confidence"] == 0.21
    assert "sensorConsistency" not in visual
    assert "trustScore" not in body
    assert "authenticity" not in body

    inspector = client.get(
        f"/api/v1/sessions/{session_id}/visual-analysis",
        headers=inspector_headers,
    )
    assert inspector.status_code == 403

    # Keep the seeded object referenced so the test setup is explicit about organization scope.
    assert identities["admin"].organization_id == identities["inspector"].organization_id
