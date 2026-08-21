from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.models.advanced_security import AdvancedSecurityResult
from app.models.advanced_signals import AdvancedSignalResult
from app.models.challenge import VerificationChallenge
from app.models.fusion import VisualInertialResult
from app.models.verification import EvidenceFile, EvidenceFileType, EvidenceUploadStatus, VerificationSession
from app.models.visual_motion import VisualMotionResult
from app.services.audit_service import record_audit
from app.services.storage_service import StorageService, get_storage_service
from app.services.verification.advanced.environment_signal import analyze_environment_metadata
from app.services.verification.advanced.io import read_json_object
from app.services.verification.advanced.statistical_anomaly import analyze_statistical_anomaly

ANALYSIS_VERSION = "advanced-signals-v1.0"
MAX_METADATA_BYTES = 2 * 1024 * 1024


def _metadata(
    db: Session,
    session_id: uuid.UUID,
    storage: StorageService,
) -> dict:
    row = db.scalar(
        select(EvidenceFile).where(
            EvidenceFile.session_id == session_id,
            EvidenceFile.file_type == EvidenceFileType.SESSION_METADATA,
            EvidenceFile.upload_status == EvidenceUploadStatus.UPLOADED,
            EvidenceFile.hash_verified.is_(True),
        )
    )
    if row is None:
        return {}
    try:
        return read_json_object(storage, row, max_bytes=MAX_METADATA_BYTES)
    except (OSError, ValueError):
        return {}


def _terminal_fusion_rows(db: Session, session_id: uuid.UUID) -> list[VisualInertialResult]:
    challenges = list(
        db.scalars(
            select(VerificationChallenge)
            .where(VerificationChallenge.session_id == session_id)
            .order_by(VerificationChallenge.sequence_number, VerificationChallenge.attempt_number)
        ).all()
    )
    latest: dict[int, VerificationChallenge] = {}
    for challenge in challenges:
        current = latest.get(challenge.sequence_number)
        if current is None or challenge.attempt_number > current.attempt_number:
            latest[challenge.sequence_number] = challenge
    ids = {challenge.id for challenge in latest.values()}
    if not ids:
        return []
    return list(
        db.scalars(
            select(VisualInertialResult).where(
                VisualInertialResult.session_id == session_id,
                VisualInertialResult.challenge_id.in_(ids),
                VisualInertialResult.fusion_version == get_settings().fusion_analysis_version,
            )
        ).all()
    )


def _duplicate_ratio(db: Session, session_id: uuid.UUID) -> float:
    values = list(
        db.scalars(
            select(VisualMotionResult.duplicate_frame_ratio).where(
                VisualMotionResult.session_id == session_id
            )
        ).all()
    )
    return max((float(value or 0.0) for value in values), default=0.0)


def _latest_phase9(db: Session, session_id: uuid.UUID) -> AdvancedSecurityResult | None:
    return db.scalar(
        select(AdvancedSecurityResult)
        .where(AdvancedSecurityResult.session_id == session_id)
        .order_by(AdvancedSecurityResult.updated_at.desc())
    )


def analyze_advanced_signals(
    db: Session,
    session_id: uuid.UUID,
    *,
    force: bool = False,
    storage: StorageService | None = None,
) -> AdvancedSignalResult:
    session = db.get(VerificationSession, session_id)
    if session is None:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")

    existing = db.scalar(
        select(AdvancedSignalResult).where(
            AdvancedSignalResult.session_id == session.id,
            AdvancedSignalResult.algorithm_version == ANALYSIS_VERSION,
        )
    )
    if existing is not None and not force:
        return existing

    object_storage = storage or get_storage_service()
    environment = analyze_environment_metadata(_metadata(db, session.id, object_storage))
    phase9 = _latest_phase9(db, session.id)
    fusion_rows = _terminal_fusion_rows(db, session.id)
    duplicate_ratio = _duplicate_ratio(db, session.id)

    anomaly = analyze_statistical_anomaly(
        sensor_anomaly_score=float(phase9.sensor_anomaly_score) if phase9 is not None else 0.0,
        location_risk_score=float(phase9.location_risk_score) if phase9 is not None else 0.0,
        duplicate_frame_ratio=duplicate_ratio,
        environment_risk_score=float(environment["risk_score"]),
        environment_confidence=float(environment["confidence"]),
        fusion_rows=fusion_rows,
    )

    codes = list(dict.fromkeys(environment["reason_codes"] + anomaly["reason_codes"]))
    reasons = list(dict.fromkeys(environment["reasons"] + anomaly["reasons"]))
    if phase9 is None:
        codes.append("PHASE9_SECURITY_UNAVAILABLE")
        reasons.append("Phase 9 security analysis was unavailable, so Phase 10 used the remaining signals only.")

    metrics = {
        "environment": environment["metrics"],
        "statisticalAnomaly": anomaly["metrics"],
        "supportingEvidenceOnly": True,
        "phase9Available": phase9 is not None,
        "duplicateFrameRatio": duplicate_ratio,
    }

    row = existing or AdvancedSignalResult(
        organization_id=session.organization_id,
        inspection_id=session.inspection_id,
        session_id=session.id,
        process_status="COMPLETE",
        environment_status=str(environment["status"]),
        environment_consistency_score=environment["consistency_score"],
        environment_risk_score=float(environment["risk_score"]),
        environment_confidence=float(environment["confidence"]),
        statistical_anomaly_status=str(anomaly["status"]),
        statistical_anomaly_score=float(anomaly["score"]),
        statistical_anomaly_confidence=float(anomaly["confidence"]),
        algorithm_version=ANALYSIS_VERSION,
    )
    row.process_status = "COMPLETE"
    row.environment_status = str(environment["status"])
    row.environment_consistency_score = environment["consistency_score"]
    row.environment_risk_score = float(environment["risk_score"])
    row.environment_confidence = float(environment["confidence"])
    row.statistical_anomaly_status = str(anomaly["status"])
    row.statistical_anomaly_score = float(anomaly["score"])
    row.statistical_anomaly_confidence = float(anomaly["confidence"])
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
        action="ADVANCED_SIGNALS_ANALYZED",
        metadata={
            "algorithmVersion": ANALYSIS_VERSION,
            "environmentStatus": row.environment_status,
            "environmentConsistency": row.environment_consistency_score,
            "statisticalAnomalyStatus": row.statistical_anomaly_status,
            "statisticalAnomalyScore": round(row.statistical_anomaly_score, 6),
        },
    )
    db.commit()
    db.refresh(row)
    return row
