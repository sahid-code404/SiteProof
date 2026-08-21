import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.challenge import ChallengeType, VerificationChallenge
from app.models.fusion import ConsistencyStatus, FusionAnalysisStatus, VisualInertialResult
from app.models.user import User, UserRole
from app.models.verification import (
    EvidenceFile,
    EvidenceFileType,
    EvidenceUploadStatus,
    VerificationSession,
    VerificationSessionStatus,
)
from app.models.visual_motion import (
    VisualAnalysisStatus,
    VisualDirection,
    VisualMotionResult,
    VisualQuality,
)
from app.services.fusion.service import analyze_session_fusion
from app.services.storage_service import LocalObjectStorage
from tests.phase3_helpers import (
    PASSWORD,
    create_ready_inspection,
    create_session,
    finish_capture,
    login,
    seed_identities,
    start_capture,
)
from tests.phase4_helpers import synthetic_sensor_body


def _expected_visual_direction(challenge_type: ChallengeType) -> VisualDirection:
    # Phase 5 v1.2+ reports rear-camera optical pitch for tilt, which is opposite the
    # physical top-edge challenge label. Fusion normalizes this at its boundary.
    return {
        ChallengeType.ROTATE_RIGHT: VisualDirection.RIGHT,
        ChallengeType.ROTATE_LEFT: VisualDirection.LEFT,
        ChallengeType.TILT_UP: VisualDirection.DOWN,
        ChallengeType.TILT_DOWN: VisualDirection.UP,
    }[challenge_type]


def _continuous_sensor_evidence(
    challenges: list[VerificationChallenge],
    session: VerificationSession,
) -> bytes:
    rows = []
    assert session.capture_anchor_monotonic_ns is not None
    for challenge in challenges:
        assert challenge.client_start_monotonic_ns is not None
        start_relative_ns = (
            challenge.client_start_monotonic_ns - session.capture_anchor_monotonic_ns
        )
        payload = synthetic_sensor_body(
            {
                "challengeId": str(challenge.id),
                "type": challenge.challenge_type.value,
                "parameters": challenge.parameters_json,
                "nonce": challenge.nonce,
            },
            start_relative_ns=start_relative_ns,
        )
        rows.extend(
            sample
            for sample in payload["samples"]
            if sample["type"] == "GYROSCOPE"
        )
    rows.sort(key=lambda item: item["relativeTimestampNs"])
    encoded = (
        "\n".join(json.dumps(item, separators=(",", ":")) for item in rows) + "\n"
    ).encode()
    return gzip.compress(encoded)


def _visual_curve(start_ms: int) -> list[dict]:
    points = []
    for offset in range(0, 2001, 100):
        value = 0.0 if offset < 600 or offset > 1600 else 1.0
        points.append({"timeMs": start_ms + offset, "magnitudePx": value * 6.0})
    return points


def _prepare_fusion_inputs(client, db, tmp_path: Path):
    identities = seed_identities(db)
    reviewer = User(
        organization_id=identities["org"].id,
        email=f"reviewer-{identities['org'].id}@example.com",
        full_name="Reviewer",
        hashed_password=hash_password(PASSWORD),
        role=UserRole.REVIEWER,
        is_active=True,
    )
    db.add(reviewer)
    db.commit()

    admin_headers = login(client, identities["admin"])
    reviewer_headers = login(client, reviewer)
    inspector_headers = login(client, identities["inspector"])
    other_admin_headers = login(client, identities["other_admin"])

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
    completed = finish_capture(client, inspector_headers, session_id)
    assert completed.status_code == 200, completed.text

    session = db.get(VerificationSession, session_id)
    assert session is not None
    challenges = list(
        db.scalars(
            select(VerificationChallenge)
            .where(VerificationChallenge.session_id == session.id)
            .order_by(
                VerificationChallenge.sequence_number,
                VerificationChallenge.attempt_number,
            )
        ).all()
    )
    latest: dict[int, VerificationChallenge] = {}
    for challenge in challenges:
        latest[challenge.sequence_number] = challenge
    terminal = [latest[key] for key in sorted(latest)]
    assert len(terminal) == 3

    storage = LocalObjectStorage(str(tmp_path / "objects"))
    sensor_bytes = _continuous_sensor_evidence(terminal, session)
    sensor_path = tmp_path / "sensors.ndjson.gz"
    sensor_path.write_bytes(sensor_bytes)
    sensor_key = f"{session.organization_id}/{session.id}/sensors.ndjson.gz"
    storage.put_file(sensor_path, sensor_key, "application/octet-stream")

    session.status = VerificationSessionStatus.UPLOADED
    session.uploaded_at = datetime.now(timezone.utc)
    db.add(
        EvidenceFile(
            organization_id=session.organization_id,
            inspection_id=session.inspection_id,
            session_id=session.id,
            file_type=EvidenceFileType.SENSOR_DATA,
            storage_key=sensor_key,
            original_filename="sensors.ndjson.gz",
            mime_type="application/octet-stream",
            size_bytes=len(sensor_bytes),
            sha256=hashlib.sha256(sensor_bytes).hexdigest(),
            upload_status=EvidenceUploadStatus.UPLOADED,
            hash_verified=True,
            uploaded_at=datetime.now(timezone.utc),
        )
    )

    assert session.capture_anchor_monotonic_ns is not None
    for challenge in terminal:
        assert challenge.client_start_monotonic_ns is not None
        start_ms = int(
            round(
                (
                    challenge.client_start_monotonic_ns
                    - session.capture_anchor_monotonic_ns
                )
                / 1_000_000.0
            )
        )
        metrics = challenge.metrics_json or {}
        angles = [
            float(value)
            for value in (
                metrics.get("observedGyroDegrees"),
                metrics.get("observedRotationVectorDegrees"),
            )
            if isinstance(value, (int, float))
        ]
        assert angles
        sensor_angle = sum(angles) / len(angles)
        db.add(
            VisualMotionResult(
                organization_id=session.organization_id,
                session_id=session.id,
                challenge_id=challenge.id,
                analysis_version=get_settings().vision_analysis_version,
                analysis_status=VisualAnalysisStatus.SUCCESS,
                visual_direction=_expected_visual_direction(challenge.challenge_type),
                visual_quality=VisualQuality.GOOD,
                estimated_rotation_degrees=max(0.0, abs(sensor_angle) - 2.0),
                motion_start_ms=start_ms + 600,
                motion_end_ms=start_ms + 1980,
                feature_count=160,
                tracked_feature_count=110,
                inlier_ratio=0.88,
                visual_confidence=0.90,
                scene_continuity_score=0.96,
                duplicate_frame_ratio=0.0,
                freeze_duration_ms=0,
                invalid_frame_ratio=0.0,
                diagnostics_json={
                    "motionCurve": _visual_curve(start_ms),
                    "timeline": {
                        "challengeStartSessionMs": start_ms,
                        "challengeEndSessionMs": start_ms + 2000,
                    },
                    "reasons": ["Synthetic current Phase 5 fixture for fusion integration test."],
                },
            )
        )
    db.commit()
    return {
        "identities": identities,
        "session": session,
        "challenges": terminal,
        "storage": storage,
        "admin_headers": admin_headers,
        "reviewer_headers": reviewer_headers,
        "inspector_headers": inspector_headers,
        "other_admin_headers": other_admin_headers,
    }


def test_phase4_plus_phase5_inputs_produce_persisted_idempotent_fusion_and_api(
    client,
    db,
    tmp_path,
):
    data = _prepare_fusion_inputs(client, db, tmp_path)
    session = data["session"]

    before = client.get(
        f"/api/v1/sessions/{session.id}/fusion-analysis",
        headers=data["reviewer_headers"],
    )
    assert before.status_code == 200, before.text
    assert before.json()["status"] == "PENDING"
    assert before.json()["challenges"] == []

    analyze_session_fusion(db, session.id, storage=data["storage"])

    rows = list(
        db.scalars(
            select(VisualInertialResult)
            .where(VisualInertialResult.session_id == session.id)
            .order_by(VisualInertialResult.created_at)
        ).all()
    )
    assert len(rows) == 3
    assert all(row.analysis_status == FusionAnalysisStatus.COMPLETE for row in rows)
    assert all(
        row.consistency_status
        in {
            ConsistencyStatus.CONSISTENT,
            ConsistencyStatus.PARTIALLY_CONSISTENT,
        }
        for row in rows
    )
    assert all(row.fusion_version == "fusion-v1.0" for row in rows)
    assert all(row.angle_difference_deg is not None for row in rows)
    assert all(row.motion_curve_correlation is not None for row in rows)
    assert all(row.fusion_confidence is not None for row in rows)

    analyze_session_fusion(db, session.id, storage=data["storage"])
    second_count = len(
        list(
            db.scalars(
                select(VisualInertialResult).where(
                    VisualInertialResult.session_id == session.id
                )
            ).all()
        )
    )
    assert second_count == 3

    response = client.get(
        f"/api/v1/sessions/{session.id}/fusion-analysis",
        headers=data["reviewer_headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "COMPLETE"
    assert body["fusionVersion"] == "fusion-v1.0"
    assert len(body["challenges"]) == 3
    assert body["summary"]["challengeCount"] == 3
    assert body["summary"]["meanConsistencyScore"] is not None
    assert all(item["sensorCurve"] for item in body["challenges"])
    assert all(item["visualCurve"] for item in body["challenges"])
    assert "verified" not in json.dumps(body).lower()
    assert "trustScore" not in body

    inspector = client.get(
        f"/api/v1/sessions/{session.id}/fusion-analysis",
        headers=data["inspector_headers"],
    )
    assert inspector.status_code == 403

    other_org = client.get(
        f"/api/v1/sessions/{session.id}/fusion-analysis",
        headers=data["other_admin_headers"],
    )
    assert other_org.status_code == 404

    admin = client.get(
        f"/api/v1/sessions/{session.id}/fusion-analysis",
        headers=data["admin_headers"],
    )
    assert admin.status_code == 200


def test_visual_inconclusive_forces_fusion_inconclusive(client, db, tmp_path):
    data = _prepare_fusion_inputs(client, db, tmp_path)
    session = data["session"]
    first = db.scalar(
        select(VisualMotionResult)
        .where(VisualMotionResult.session_id == session.id)
        .order_by(VisualMotionResult.created_at)
    )
    assert first is not None
    first.analysis_status = VisualAnalysisStatus.INCONCLUSIVE
    first.visual_quality = VisualQuality.POOR
    first.visual_confidence = 0.2
    db.commit()

    analyze_session_fusion(db, session.id, storage=data["storage"])
    result = db.scalar(
        select(VisualInertialResult).where(
            VisualInertialResult.challenge_id == first.challenge_id
        )
    )
    assert result is not None
    assert result.analysis_status == FusionAnalysisStatus.COMPLETE
    assert result.consistency_status == ConsistencyStatus.INCONCLUSIVE
    assert "LOW_VISUAL_QUALITY" in (result.mismatch_reasons_json or [])
