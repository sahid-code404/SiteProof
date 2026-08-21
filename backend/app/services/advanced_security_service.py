from __future__ import annotations

import uuid
from statistics import fmean
from typing import Any

import cv2
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.models.advanced_security import (
    AdvancedProcessStatus,
    AdvancedSecurityResult,
    DeviceAttestation,
    LocationRiskResult,
    ReplayRiskResult,
    RiskLevel,
    SensorAnomalyResult,
)
from app.models.challenge import VerificationChallenge
from app.models.fusion import (
    ConsistencyStatus,
    MismatchReason,
    MotionDirection,
    VisualInertialResult,
)
from app.models.verification import EvidenceFile, EvidenceFileType, EvidenceUploadStatus, VerificationSession
from app.models.visual_motion import VisualMotionResult
from app.services.audit_service import record_audit
from app.services.storage_service import StorageService, get_storage_service
from app.services.verification.advanced.device_metadata import analyze_device_metadata
from app.services.verification.advanced.evidence_reuse import analyze_exact_evidence_reuse
from app.services.verification.advanced.io import materialized_path, read_json_array, read_json_object, read_ndjson
from app.services.verification.advanced.location_risk import analyze_location_samples
from app.services.verification.advanced.replay_risk import analyze_frames
from app.services.verification.advanced.sensor_anomaly import analyze_sensor_stream

ANALYSIS_VERSION = "advanced-security-v1.1"
MAX_SENSOR_BYTES = 64 * 1024 * 1024
MAX_LOCATION_BYTES = 8 * 1024 * 1024
MAX_METADATA_BYTES = 2 * 1024 * 1024
VIDEO_SAMPLE_COUNT = 8


def _evidence_by_type(db: Session, session_id: uuid.UUID) -> dict[EvidenceFileType, EvidenceFile]:
    rows = list(
        db.scalars(
            select(EvidenceFile).where(
                EvidenceFile.session_id == session_id,
                EvidenceFile.upload_status == EvidenceUploadStatus.UPLOADED,
                EvidenceFile.hash_verified.is_(True),
            )
        ).all()
    )
    return {row.file_type: row for row in rows}


def _sample_video_frames(path, *, max_frames: int = VIDEO_SAMPLE_COUNT) -> list[Any]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return []
    try:
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frames: list[Any] = []
        if count > 0:
            if max_frames == 1:
                indexes = [max(0, count // 2)]
            else:
                indexes = [int(round(index * max(0, count - 1) / (max_frames - 1))) for index in range(max_frames)]
            for frame_index in sorted(set(indexes)):
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ok, frame = capture.read()
                if ok and frame is not None:
                    frames.append(frame)
            return frames

        while len(frames) < max_frames:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            frames.append(frame)
        return frames
    finally:
        capture.release()


def _fusion_row_replay_risk(row: VisualInertialResult) -> float:
    """Map one Phase 6 result to replay risk without confusing camera metrology with liveness.

    Phase 5's visual angle is an approximate projective estimate. A hand jerk, rolling-shutter
    artifact or feature-window truncation can make that angle much smaller than the gyroscope
    angle while both sources still agree on physical direction. That is useful verification
    quality evidence, but it is not by itself strong evidence that a screen replay occurred.
    """
    reasons = set(row.mismatch_reasons_json or [])
    same_direction = (
        row.sensor_direction == row.visual_direction
        and row.sensor_direction not in {MotionDirection.NONE, MotionDirection.MIXED}
    )

    if MismatchReason.OPPOSITE_DIRECTION.value in reasons:
        return 1.0

    motion_absence_reasons = {
        MismatchReason.VISUAL_WITHOUT_SENSOR_MOTION.value,
        MismatchReason.SENSOR_WITHOUT_VISUAL_MOTION.value,
    }
    if reasons & motion_absence_reasons and not same_direction:
        return 0.95

    if row.effective_consistency_score is not None:
        disagreement = max(0.0, min(1.0, 1.0 - float(row.effective_consistency_score)))
    elif row.consistency_status == ConsistencyStatus.MISMATCH:
        disagreement = 0.75
    elif row.consistency_status == ConsistencyStatus.PARTIALLY_CONSISTENT:
        disagreement = 0.45
    elif row.consistency_status == ConsistencyStatus.INCONCLUSIVE:
        disagreement = 0.40
    else:
        disagreement = 0.0

    if same_direction:
        # Same-direction disagreement is a corroborating quality/timing signal. Cap it below
        # the strong replay threshold so magnitude/timing noise cannot independently accuse.
        return min(disagreement, 0.55)
    if row.consistency_status == ConsistencyStatus.MISMATCH:
        return max(disagreement, 0.75)
    return disagreement


def _fusion_mismatch_score(db: Session, session_id: uuid.UUID) -> float:
    challenge_rows = list(
        db.scalars(
            select(VerificationChallenge)
            .where(VerificationChallenge.session_id == session_id)
            .order_by(
                VerificationChallenge.sequence_number,
                VerificationChallenge.attempt_number,
            )
        ).all()
    )
    latest: dict[int, VerificationChallenge] = {}
    for challenge in challenge_rows:
        current = latest.get(challenge.sequence_number)
        if current is None or challenge.attempt_number > current.attempt_number:
            latest[challenge.sequence_number] = challenge
    latest_ids = {challenge.id for challenge in latest.values()}
    if not latest_ids:
        return 0.0

    rows = list(
        db.scalars(
            select(VisualInertialResult).where(
                VisualInertialResult.session_id == session_id,
                VisualInertialResult.fusion_version == get_settings().fusion_analysis_version,
                VisualInertialResult.challenge_id.in_(latest_ids),
            )
        ).all()
    )
    return max((_fusion_row_replay_risk(row) for row in rows), default=0.0)


def _duplicate_frame_ratio(db: Session, session_id: uuid.UUID) -> float:
    values = list(
        db.scalars(
            select(VisualMotionResult.duplicate_frame_ratio).where(
                VisualMotionResult.session_id == session_id
            )
        ).all()
    )
    return max((float(value or 0.0) for value in values), default=0.0)


def _latest_attestation(db: Session, session_id: uuid.UUID) -> DeviceAttestation | None:
    return db.scalar(
        select(DeviceAttestation)
        .where(DeviceAttestation.session_id == session_id)
        .order_by(DeviceAttestation.validated_at.desc())
    )


def _risk_from_parts(
    location: dict[str, Any],
    sensor: dict[str, Any],
    replay: dict[str, Any],
    device: dict[str, Any],
) -> RiskLevel:
    levels = {location["risk_level"], sensor["risk_level"], replay["risk_level"]}
    if RiskLevel.HIGH in levels or float(device["risk_score"]) >= 0.75:
        return RiskLevel.HIGH
    if RiskLevel.MODERATE in levels or float(device["risk_score"]) >= 0.35:
        return RiskLevel.MODERATE
    if levels == {RiskLevel.INCONCLUSIVE}:
        return RiskLevel.INCONCLUSIVE
    return RiskLevel.LOW


def _set_location_row(row: LocationRiskResult, result: dict[str, Any]) -> None:
    row.process_status = result["process_status"]
    row.risk_level = result["risk_level"]
    row.score = result["score"]
    row.confidence = result["confidence"]
    row.mock_location_detected = result["mock_location_detected"]
    row.max_implied_speed = result["max_implied_speed"]
    row.impossible_jump_count = result["impossible_jump_count"]
    row.sensor_location_consistency = result["sensor_location_consistency"]
    row.reason_codes_json = result["reason_codes"]
    row.reasons_json = result["reasons"]
    row.metrics_json = result["metrics"]


def _set_sensor_row(row: SensorAnomalyResult, result: dict[str, Any]) -> None:
    row.process_status = result["process_status"]
    row.risk_level = result["risk_level"]
    row.status = result["status"]
    row.anomaly_score = result["anomaly_score"]
    row.confidence = result["confidence"]
    row.duplicate_sequence_score = result["duplicate_sequence_score"]
    row.timestamp_anomaly_score = result["timestamp_anomaly_score"]
    row.range_anomaly_score = result["range_anomaly_score"]
    row.cross_sensor_conflict_score = result["cross_sensor_conflict_score"]
    row.reason_codes_json = result["reason_codes"]
    row.reasons_json = result["reasons"]
    row.metrics_json = result["metrics"]


def _set_replay_row(row: ReplayRiskResult, result: dict[str, Any]) -> None:
    row.process_status = result["process_status"]
    row.risk_level = result["risk_level"]
    row.score = result["score"]
    row.confidence = result["confidence"]
    row.display_rectangle_score = result["display_rectangle_score"]
    row.moire_score = result["moire_score"]
    row.banding_score = result["banding_score"]
    row.evidence_reuse_score = result["evidence_reuse_score"]
    row.fusion_mismatch_score = result["fusion_mismatch_score"]
    row.reason_codes_json = result["reason_codes"]
    row.reasons_json = result["reasons"]
    row.metrics_json = result["metrics"]


def analyze_advanced_security(
    db: Session,
    session_id: uuid.UUID,
    *,
    force: bool = False,
    storage: StorageService | None = None,
) -> AdvancedSecurityResult:
    session = db.get(VerificationSession, session_id)
    if session is None:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")

    existing = db.scalar(
        select(AdvancedSecurityResult).where(
            AdvancedSecurityResult.session_id == session.id,
            AdvancedSecurityResult.algorithm_version == ANALYSIS_VERSION,
        )
    )
    if existing is not None and not force:
        return existing

    evidence = _evidence_by_type(db, session.id)
    object_storage = storage or get_storage_service()
    sensor_rows: list[dict[str, Any]] = []
    location_rows: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}

    sensor_file = evidence.get(EvidenceFileType.SENSOR_DATA)
    if sensor_file is not None:
        try:
            sensor_rows = read_ndjson(object_storage, sensor_file, max_bytes=MAX_SENSOR_BYTES)
        except (OSError, ValueError):
            sensor_rows = []

    location_file = evidence.get(EvidenceFileType.LOCATION_DATA)
    if location_file is not None:
        try:
            location_rows = read_json_array(object_storage, location_file, max_bytes=MAX_LOCATION_BYTES)
        except (OSError, ValueError):
            location_rows = []

    metadata_file = evidence.get(EvidenceFileType.SESSION_METADATA)
    if metadata_file is not None:
        try:
            metadata = read_json_object(object_storage, metadata_file, max_bytes=MAX_METADATA_BYTES)
        except (OSError, ValueError):
            metadata = {}

    location_result = analyze_location_samples(location_rows, sensor_rows)
    sensor_result = analyze_sensor_stream(sensor_rows)
    reuse_result = analyze_exact_evidence_reuse(
        db,
        organization_id=session.organization_id,
        session_id=session.id,
    )

    frames: list[Any] = []
    video_file = evidence.get(EvidenceFileType.VIDEO)
    if video_file is not None:
        temp = None
        try:
            path, temp = materialized_path(object_storage, video_file)
            frames = _sample_video_frames(path)
        except (OSError, ValueError):
            frames = []
        finally:
            if temp is not None:
                temp.cleanup()

    fusion_mismatch = _fusion_mismatch_score(db, session.id)
    duplicate_ratio = _duplicate_frame_ratio(db, session.id)
    replay_result = analyze_frames(
        frames,
        fusion_mismatch_score=fusion_mismatch,
        duplicate_frame_ratio=duplicate_ratio,
        evidence_reuse_score=float(reuse_result["score"]),
    )
    device_result = analyze_device_metadata(metadata, _latest_attestation(db, session.id))

    location_row = db.scalar(
        select(LocationRiskResult).where(
            LocationRiskResult.session_id == session.id,
            LocationRiskResult.algorithm_version == location_result["algorithm_version"],
        )
    ) or LocationRiskResult(
        organization_id=session.organization_id,
        session_id=session.id,
        algorithm_version=location_result["algorithm_version"],
        process_status=location_result["process_status"],
        risk_level=location_result["risk_level"],
        score=location_result["score"],
        confidence=location_result["confidence"],
    )
    _set_location_row(location_row, location_result)
    db.add(location_row)

    sensor_row = db.scalar(
        select(SensorAnomalyResult).where(
            SensorAnomalyResult.session_id == session.id,
            SensorAnomalyResult.algorithm_version == sensor_result["algorithm_version"],
        )
    ) or SensorAnomalyResult(
        organization_id=session.organization_id,
        session_id=session.id,
        algorithm_version=sensor_result["algorithm_version"],
        process_status=sensor_result["process_status"],
        risk_level=sensor_result["risk_level"],
        status=sensor_result["status"],
        anomaly_score=sensor_result["anomaly_score"],
        confidence=sensor_result["confidence"],
    )
    _set_sensor_row(sensor_row, sensor_result)
    db.add(sensor_row)

    replay_row = db.scalar(
        select(ReplayRiskResult).where(
            ReplayRiskResult.session_id == session.id,
            ReplayRiskResult.algorithm_version == replay_result["algorithm_version"],
        )
    ) or ReplayRiskResult(
        organization_id=session.organization_id,
        session_id=session.id,
        algorithm_version=replay_result["algorithm_version"],
        process_status=replay_result["process_status"],
        risk_level=replay_result["risk_level"],
        score=replay_result["score"],
        confidence=replay_result["confidence"],
    )
    _set_replay_row(replay_row, replay_result)
    db.add(replay_row)

    overall_risk = _risk_from_parts(location_result, sensor_result, replay_result, device_result)
    confidence_values = [
        float(location_result["confidence"]),
        float(sensor_result["confidence"]),
        float(replay_result["confidence"]),
        float(device_result["confidence"]),
    ]
    overall_confidence = fmean(confidence_values)
    codes = sorted(
        set(
            location_result["reason_codes"]
            + sensor_result["reason_codes"]
            + replay_result["reason_codes"]
            + reuse_result["reason_codes"]
            + device_result["reason_codes"]
        )
    )
    reasons = list(
        dict.fromkeys(
            location_result["reasons"]
            + sensor_result["reasons"]
            + replay_result["reasons"]
            + device_result["reasons"]
        )
    )
    metrics = {
        "location": location_result["metrics"],
        "sensor": sensor_result["metrics"],
        "replay": replay_result["metrics"],
        "evidenceReuse": reuse_result["metrics"],
        "device": device_result["metrics"],
        "fusionMismatchScore": fusion_mismatch,
        "duplicateFrameRatio": duplicate_ratio,
    }

    row = existing or AdvancedSecurityResult(
        organization_id=session.organization_id,
        inspection_id=session.inspection_id,
        session_id=session.id,
        algorithm_version=ANALYSIS_VERSION,
        process_status=AdvancedProcessStatus.COMPLETE,
        overall_risk=overall_risk,
        confidence=overall_confidence,
        location_risk_score=float(location_result["score"]),
        sensor_anomaly_score=float(sensor_result["anomaly_score"]),
        replay_risk_score=float(replay_result["score"]),
        evidence_reuse_score=float(reuse_result["score"]),
        device_integrity_status=str(device_result["status"]),
        device_risk_score=float(device_result["risk_score"]),
    )
    row.process_status = AdvancedProcessStatus.COMPLETE
    row.overall_risk = overall_risk
    row.confidence = overall_confidence
    row.location_risk_score = float(location_result["score"])
    row.sensor_anomaly_score = float(sensor_result["anomaly_score"])
    row.replay_risk_score = float(replay_result["score"])
    row.evidence_reuse_score = float(reuse_result["score"])
    row.device_integrity_status = str(device_result["status"])
    row.device_risk_score = float(device_result["risk_score"])
    row.reason_codes_json = codes
    row.reasons_json = reasons
    row.metrics_json = metrics
    db.add(row)
    db.flush()

    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=session.created_by_user_id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="ADVANCED_SECURITY_ANALYZED",
        metadata={
            "algorithmVersion": ANALYSIS_VERSION,
            "overallRisk": overall_risk.value,
            "confidence": round(overall_confidence, 6),
            "reasonCodes": codes,
        },
    )
    db.commit()
    db.refresh(row)
    return row
