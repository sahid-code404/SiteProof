import logging
import time
import uuid
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.db.session import SessionLocal
from app.models.challenge import ChallengeResult, VerificationChallenge
from app.models.fusion import (
    ConsistencyStatus,
    FusionAnalysisStatus,
    MismatchReason,
    MotionDirection,
    VisualInertialResult,
)
from app.models.user import User
from app.models.verification import (
    EvidenceFile,
    EvidenceFileType,
    EvidenceUploadStatus,
    VerificationSession,
)
from app.models.visual_motion import VisualAnalysisStatus, VisualMotionResult
from app.schemas.fusion_analysis import (
    FusionAnalysisResponse,
    FusionChallengeAnalysisItem,
    FusionCurvePoint,
    FusionSessionSummary,
)
from app.services.audit_service import record_audit
from app.services.fusion.aggregator import decide_fusion
from app.services.fusion.comparators import (
    correlation_consistency,
    direction_consistency,
    duration_consistency,
    magnitude_consistency,
    temporal_consistency,
)
from app.services.fusion.normalizer import normalize_sensor_motion, normalize_visual_motion
from app.services.fusion.sensor_evidence import (
    challenge_window_ms,
    extract_sensor_curve,
    load_gyroscope_samples,
)
from app.services.fusion.temporal import compare_motion_curves
from app.services.storage_service import StorageService, get_storage_service

logger = logging.getLogger("siteproof.fusion")


def _latest_challenges(db: Session, session_id: uuid.UUID) -> list[VerificationChallenge]:
    rows = list(
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
    for row in rows:
        current = latest.get(row.sequence_number)
        if current is None or row.attempt_number > current.attempt_number:
            latest[row.sequence_number] = row
    return [latest[key] for key in sorted(latest)]


def _visual_results(db: Session, session_id: uuid.UUID) -> dict[uuid.UUID, VisualMotionResult]:
    version = get_settings().vision_analysis_version
    return {
        row.challenge_id: row
        for row in db.scalars(
            select(VisualMotionResult).where(
                VisualMotionResult.session_id == session_id,
                VisualMotionResult.analysis_version == version,
            )
        ).all()
    }


def _sensor_record(db: Session, session_id: uuid.UUID) -> EvidenceFile:
    record = db.scalar(
        select(EvidenceFile).where(
            EvidenceFile.session_id == session_id,
            EvidenceFile.file_type == EvidenceFileType.SENSOR_DATA,
        )
    )
    if (
        record is None
        or record.upload_status != EvidenceUploadStatus.UPLOADED
        or not record.hash_verified
    ):
        raise ValueError("Verified full sensor evidence is unavailable for fusion analysis")
    return record


def _current_result(
    db: Session,
    challenge_id: uuid.UUID,
) -> VisualInertialResult | None:
    return db.scalar(
        select(VisualInertialResult).where(
            VisualInertialResult.challenge_id == challenge_id,
            VisualInertialResult.fusion_version == get_settings().fusion_analysis_version,
        )
    )


def _upsert(
    db: Session,
    *,
    session: VerificationSession,
    challenge: VerificationChallenge,
) -> VisualInertialResult:
    result = _current_result(db, challenge.id)
    if result is None:
        result = VisualInertialResult(
            organization_id=session.organization_id,
            session_id=session.id,
            challenge_id=challenge.id,
            fusion_version=get_settings().fusion_analysis_version,
            analysis_status=FusionAnalysisStatus.PENDING,
            consistency_status=ConsistencyStatus.INCONCLUSIVE,
            sensor_direction=MotionDirection.NONE,
            visual_direction=MotionDirection.NONE,
        )
        db.add(result)
    return result


def _reset_metrics(result: VisualInertialResult) -> None:
    result.sensor_direction = MotionDirection.NONE
    result.visual_direction = MotionDirection.NONE
    for field in (
        "sensor_angle_deg",
        "visual_angle_deg",
        "angle_difference_deg",
        "relative_angle_error",
        "sensor_start_ms",
        "visual_start_ms",
        "start_offset_ms",
        "sensor_peak_ms",
        "visual_peak_ms",
        "sensor_end_ms",
        "visual_end_ms",
        "end_offset_ms",
        "sensor_duration_ms",
        "visual_duration_ms",
        "motion_curve_correlation",
        "best_lag_ms",
        "direction_score",
        "magnitude_score",
        "timing_score",
        "duration_score",
        "correlation_score",
        "raw_consistency_score",
        "effective_consistency_score",
        "fusion_confidence",
    ):
        setattr(result, field, None)
    result.sensor_confidence = 0.0
    result.visual_confidence = 0.0
    result.mismatch_reasons_json = []
    result.diagnostics_json = {}


def _mark_pending(
    db: Session,
    *,
    session: VerificationSession,
    challenge: VerificationChallenge,
    reason: str,
) -> None:
    result = _upsert(db, session=session, challenge=challenge)
    _reset_metrics(result)
    result.analysis_status = FusionAnalysisStatus.PENDING
    result.consistency_status = ConsistencyStatus.INCONCLUSIVE
    result.diagnostics_json = {
        "explanations": [reason],
        "inputReady": False,
    }


def _mark_failed(
    db: Session,
    *,
    session: VerificationSession,
    challenges: list[VerificationChallenge],
    message: str,
) -> None:
    marked_any = False
    for challenge in challenges:
        result = _upsert(db, session=session, challenge=challenge)
        if result.analysis_status == FusionAnalysisStatus.COMPLETE:
            # A later challenge or reanalysis failure must not erase an already defensible
            # result from the same version. The session-level failure audit below still records
            # that the latest processing attempt did not finish cleanly.
            continue
        result.analysis_status = FusionAnalysisStatus.FAILED
        result.consistency_status = ConsistencyStatus.INCONCLUSIVE
        result.mismatch_reasons_json = []
        result.diagnostics_json = {
            "explanations": [
                "Fusion processing failed technically; this is not interpreted as suspicious evidence."
            ],
            "failure": message,
        }
        marked_any = True
        record_audit(
            db,
            organization_id=session.organization_id,
            actor_user_id=session.created_by_user_id,
            entity_type="VERIFICATION_CHALLENGE",
            entity_id=challenge.id,
            action="FUSION_ANALYSIS_FAILED",
            metadata={"fusionVersion": get_settings().fusion_analysis_version},
        )
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=session.created_by_user_id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="FUSION_ANALYSIS_FAILED",
        metadata={
            "fusionVersion": get_settings().fusion_analysis_version,
            "affectedPendingResults": marked_any,
        },
    )
    db.commit()


def _store_decision(
    result: VisualInertialResult,
    *,
    sensor,
    visual,
    magnitude,
    timing,
    duration_score,
    correlation_score,
    curves,
    decision,
    extraction,
    elapsed_ms: float,
) -> None:
    result.analysis_status = FusionAnalysisStatus.COMPLETE
    result.consistency_status = ConsistencyStatus(decision.consistency_status)
    result.sensor_direction = MotionDirection(sensor.direction)
    result.visual_direction = MotionDirection(visual.direction)
    result.sensor_angle_deg = sensor.angular_change_deg
    result.visual_angle_deg = visual.angular_change_deg
    result.angle_difference_deg = magnitude.absolute_error_deg
    result.relative_angle_error = magnitude.relative_error
    result.sensor_start_ms = sensor.start_ms
    result.visual_start_ms = visual.start_ms
    result.start_offset_ms = timing.start_offset_ms
    result.sensor_peak_ms = sensor.peak_ms
    result.visual_peak_ms = visual.peak_ms
    result.sensor_end_ms = sensor.end_ms
    result.visual_end_ms = visual.end_ms
    result.end_offset_ms = timing.end_offset_ms
    result.sensor_duration_ms = sensor.duration_ms
    result.visual_duration_ms = visual.duration_ms
    result.motion_curve_correlation = curves.best_correlation
    result.best_lag_ms = curves.best_lag_ms
    component_scores = decision.diagnostics.get("componentScores") or {}
    result.direction_score = component_scores.get("direction")
    result.magnitude_score = magnitude.score
    result.timing_score = timing.score
    result.duration_score = duration_score
    result.correlation_score = correlation_score
    result.raw_consistency_score = decision.raw_consistency_score
    result.effective_consistency_score = decision.effective_consistency_score
    result.fusion_confidence = decision.fusion_confidence
    result.sensor_confidence = sensor.confidence
    result.visual_confidence = visual.confidence
    result.mismatch_reasons_json = list(decision.mismatch_reasons)
    result.diagnostics_json = {
        **decision.diagnostics,
        "explanations": list(decision.explanations),
        "sensorCurve": [
            {"timeMs": item.time_ms, "value": round(item.value, 5)}
            for item in curves.sensor_curve
        ],
        "visualCurve": [
            {"timeMs": item.time_ms, "value": round(item.value, 5)}
            for item in curves.visual_curve
        ],
        "sensorEvidence": {
            "sampleCount": extraction.sample_count,
            "maxGapMs": extraction.max_gap_ms,
            "quality": extraction.quality,
        },
        "curve": {
            "pearsonAtZeroLag": curves.pearson_correlation,
            "bestCorrelation": curves.best_correlation,
            "bestLagMs": curves.best_lag_ms,
        },
        "processingMs": round(elapsed_ms, 3),
        "securityBoundary": (
            "Phase 6 measures cross-signal consistency only; it is not an authenticity or final trust verdict."
        ),
    }


def analyze_session_fusion(
    db: Session,
    session_id: uuid.UUID,
    *,
    storage: StorageService | None = None,
    force: bool = False,
) -> None:
    settings = get_settings()
    session = db.get(VerificationSession, session_id)
    if session is None:
        raise ValueError("Verification session does not exist")

    challenges = _latest_challenges(db, session.id)
    if not challenges:
        return

    visual_by_challenge = _visual_results(db, session.id)

    # Do not start fusion while Phase 5 is still working. Store explicit pending state so
    # reviewer polling can distinguish "not ready" from a failed comparison.
    not_ready = [
        challenge
        for challenge in challenges
        if (
            challenge.result is None
            or visual_by_challenge.get(challenge.id) is None
            or visual_by_challenge[challenge.id].analysis_status
            in {VisualAnalysisStatus.PENDING, VisualAnalysisStatus.PROCESSING}
        )
    ]
    if not_ready:
        for challenge in challenges:
            visual = visual_by_challenge.get(challenge.id)
            if (
                challenge.result is None
                or visual is None
                or visual.analysis_status in {
                    VisualAnalysisStatus.PENDING,
                    VisualAnalysisStatus.PROCESSING,
                }
            ):
                _mark_pending(
                    db,
                    session=session,
                    challenge=challenge,
                    reason="Sensor and visual challenge analysis are not both complete yet.",
                )
        db.commit()
        return

    existing = [
        _current_result(db, challenge.id)
        for challenge in challenges
    ]
    if (
        not force
        and all(
            item is not None
            and item.analysis_status == FusionAnalysisStatus.COMPLETE
            for item in existing
        )
    ):
        return

    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=session.created_by_user_id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="FUSION_ANALYSIS_STARTED",
        metadata={"fusionVersion": settings.fusion_analysis_version},
    )
    db.commit()

    try:
        object_storage = storage or get_storage_service()
        gyro_samples = load_gyroscope_samples(
            object_storage,
            _sensor_record(db, session.id),
            settings,
        )

        started_session = time.monotonic()
        for challenge in challenges:
            started_challenge = time.monotonic()
            if time.monotonic() - started_session > settings.fusion_max_processing_seconds:
                raise TimeoutError("Fusion analysis exceeded the configured processing limit")

            visual_result = visual_by_challenge[challenge.id]
            result = _upsert(db, session=session, challenge=challenge)
            result.analysis_status = FusionAnalysisStatus.PROCESSING
            db.commit()
            visual_diagnostics = visual_result.diagnostics_json or {}
            window_start, window_end = challenge_window_ms(
                challenge,
                visual_diagnostics,
                capture_anchor_monotonic_ns=session.capture_anchor_monotonic_ns,
            )
            extraction = extract_sensor_curve(
                gyro_samples,
                challenge=challenge,
                window_start_ms=window_start,
                window_end_ms=window_end,
                settings=settings,
            )
            sensor = normalize_sensor_motion(
                challenge,
                curve=extraction.curve,
                start_ms=extraction.start_ms,
                end_ms=extraction.end_ms,
                peak_ms=extraction.peak_ms,
                quality=extraction.quality,
            )
            visual = normalize_visual_motion(visual_result, challenge)

            if sensor.kind != visual.kind:
                raise ValueError("Sensor and visual motion kinds are incompatible")

            direction_score = direction_consistency(sensor, visual)
            magnitude = magnitude_consistency(sensor, visual, settings)
            timing = temporal_consistency(sensor, visual, settings)
            duration_score = duration_consistency(sensor, visual)
            curves = compare_motion_curves(
                sensor.curve,
                visual.curve,
                sample_hz=settings.fusion_resample_hz,
                max_lag_ms=settings.fusion_max_alignment_lag_ms,
            )
            correlation_score = correlation_consistency(curves.best_correlation)

            decision = decide_fusion(
                sensor=sensor,
                visual=visual,
                direction_score=direction_score,
                magnitude=magnitude,
                timing=timing,
                duration_score=duration_score,
                curves=curves,
                settings=settings,
                scene_continuity_score=visual_result.scene_continuity_score,
                freeze_duration_ms=visual_result.freeze_duration_ms,
                sensor_input_valid=challenge.result != ChallengeResult.INCONCLUSIVE,
                visual_input_valid=visual_result.analysis_status == VisualAnalysisStatus.SUCCESS,
            )
            elapsed_ms = (time.monotonic() - started_challenge) * 1000.0
            _store_decision(
                result,
                sensor=sensor,
                visual=visual,
                magnitude=magnitude,
                timing=timing,
                duration_score=duration_score,
                correlation_score=correlation_score,
                curves=curves,
                decision=decision,
                extraction=extraction,
                elapsed_ms=elapsed_ms,
            )

            audit_action = {
                ConsistencyStatus.CONSISTENT: "FUSION_ANALYSIS_COMPLETED",
                ConsistencyStatus.PARTIALLY_CONSISTENT: "FUSION_ANALYSIS_COMPLETED",
                ConsistencyStatus.INCONCLUSIVE: "FUSION_ANALYSIS_INCONCLUSIVE",
                ConsistencyStatus.MISMATCH: "FUSION_MISMATCH_DETECTED",
            }[result.consistency_status]
            record_audit(
                db,
                organization_id=session.organization_id,
                actor_user_id=session.created_by_user_id,
                entity_type="VERIFICATION_CHALLENGE",
                entity_id=challenge.id,
                action=audit_action,
                metadata={
                    "fusionVersion": settings.fusion_analysis_version,
                    "consistencyStatus": result.consistency_status.value,
                    "consistencyScore": (
                        round(result.effective_consistency_score, 4)
                        if result.effective_consistency_score is not None
                        else None
                    ),
                    "fusionConfidence": (
                        round(result.fusion_confidence, 4)
                        if result.fusion_confidence is not None
                        else None
                    ),
                    "mismatchReasons": result.mismatch_reasons_json or [],
                },
            )
            db.commit()
    except (ValueError, OSError, TimeoutError) as exc:
        _mark_failed(
            db,
            session=session,
            challenges=challenges,
            message=str(exc),
        )
        raise
    except Exception:
        _mark_failed(
            db,
            session=session,
            challenges=challenges,
            message="Unexpected fusion-analysis failure.",
        )
        raise


def run_fusion_analysis_task(session_id: uuid.UUID, *, force: bool = False) -> None:
    db = SessionLocal()
    try:
        analyze_session_fusion(db, session_id, force=force)
    except Exception:
        logger.exception("fusion analysis failed for session %s", session_id)
    finally:
        db.close()


def _overall_status(results: list[VisualInertialResult]) -> FusionAnalysisStatus:
    if not results:
        return FusionAnalysisStatus.PENDING
    states = {item.analysis_status for item in results}
    if FusionAnalysisStatus.PROCESSING in states:
        return FusionAnalysisStatus.PROCESSING
    if FusionAnalysisStatus.FAILED in states:
        return FusionAnalysisStatus.FAILED
    if FusionAnalysisStatus.PENDING in states:
        return FusionAnalysisStatus.PENDING
    return FusionAnalysisStatus.COMPLETE


def _curve_points(value: object) -> list[FusionCurvePoint]:
    if not isinstance(value, list):
        return []
    output: list[FusionCurvePoint] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        time_ms = item.get("timeMs")
        magnitude = item.get("value")
        if isinstance(time_ms, (int, float)) and isinstance(magnitude, (int, float)):
            output.append(
                FusionCurvePoint(
                    time_ms=int(round(time_ms)),
                    value=max(0.0, min(1.0, float(magnitude))),
                )
            )
    return output


def _item(
    result: VisualInertialResult,
    challenge: VerificationChallenge,
) -> FusionChallengeAnalysisItem:
    diagnostics = result.diagnostics_json or {}
    mismatch: list[MismatchReason] = []
    for raw in result.mismatch_reasons_json or []:
        try:
            mismatch.append(MismatchReason(raw))
        except ValueError:
            continue
    return FusionChallengeAnalysisItem(
        challenge_id=challenge.id,
        challenge_type=challenge.challenge_type,
        fusion_version=result.fusion_version,
        analysis_status=result.analysis_status,
        consistency_status=result.consistency_status,
        sensor_direction=result.sensor_direction,
        visual_direction=result.visual_direction,
        sensor_angle_deg=result.sensor_angle_deg,
        visual_angle_deg=result.visual_angle_deg,
        angle_difference_deg=result.angle_difference_deg,
        relative_angle_error=result.relative_angle_error,
        sensor_start_ms=result.sensor_start_ms,
        visual_start_ms=result.visual_start_ms,
        start_offset_ms=result.start_offset_ms,
        sensor_peak_ms=result.sensor_peak_ms,
        visual_peak_ms=result.visual_peak_ms,
        sensor_end_ms=result.sensor_end_ms,
        visual_end_ms=result.visual_end_ms,
        end_offset_ms=result.end_offset_ms,
        sensor_duration_ms=result.sensor_duration_ms,
        visual_duration_ms=result.visual_duration_ms,
        motion_curve_correlation=result.motion_curve_correlation,
        best_lag_ms=result.best_lag_ms,
        direction_score=result.direction_score,
        magnitude_score=result.magnitude_score,
        timing_score=result.timing_score,
        duration_score=result.duration_score,
        correlation_score=result.correlation_score,
        raw_consistency_score=result.raw_consistency_score,
        consistency_score=result.effective_consistency_score,
        fusion_confidence=result.fusion_confidence,
        sensor_confidence=result.sensor_confidence,
        visual_confidence=result.visual_confidence,
        mismatch_reasons=mismatch,
        explanations=[
            str(item)
            for item in diagnostics.get("explanations", [])
            if isinstance(item, str)
        ],
        sensor_curve=_curve_points(diagnostics.get("sensorCurve")),
        visual_curve=_curve_points(diagnostics.get("visualCurve")),
        diagnostics={
            key: value
            for key, value in diagnostics.items()
            if key not in {"sensorCurve", "visualCurve", "explanations"}
        },
    )


def _summary(items: list[FusionChallengeAnalysisItem]) -> FusionSessionSummary:
    completed = [
        item
        for item in items
        if item.analysis_status == FusionAnalysisStatus.COMPLETE
    ]
    scores = [
        item.consistency_score
        for item in completed
        if item.consistency_score is not None
    ]
    strong = {
        MismatchReason.OPPOSITE_DIRECTION,
        MismatchReason.VISUAL_WITHOUT_SENSOR_MOTION,
        MismatchReason.SENSOR_WITHOUT_VISUAL_MOTION,
    }
    return FusionSessionSummary(
        challenge_count=len(items),
        consistent=sum(item.consistency_status == ConsistencyStatus.CONSISTENT for item in completed),
        partially_consistent=sum(
            item.consistency_status == ConsistencyStatus.PARTIALLY_CONSISTENT for item in completed
        ),
        mismatch=sum(item.consistency_status == ConsistencyStatus.MISMATCH for item in completed),
        inconclusive=sum(
            item.consistency_status == ConsistencyStatus.INCONCLUSIVE for item in completed
        ),
        mean_consistency_score=fmean(scores) if scores else None,
        strong_contradiction_detected=any(
            bool(set(item.mismatch_reasons) & strong) for item in completed
        ),
    )


def get_fusion_analysis(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
) -> FusionAnalysisResponse:
    session = db.get(VerificationSession, session_id)
    if session is None or session.organization_id != current_user.organization_id:
        raise SiteProofError(
            404,
            "SESSION_NOT_FOUND",
            "Verification session was not found.",
        )

    challenges = _latest_challenges(db, session.id)
    order = {challenge.id: index for index, challenge in enumerate(challenges)}
    challenge_by_id = {challenge.id: challenge for challenge in challenges}
    rows = list(
        db.scalars(
            select(VisualInertialResult).where(
                VisualInertialResult.session_id == session.id,
                VisualInertialResult.fusion_version == get_settings().fusion_analysis_version,
            )
        ).all()
    )
    rows = [
        row for row in rows if row.challenge_id in challenge_by_id
    ]
    rows.sort(key=lambda item: order[item.challenge_id])
    items = [_item(row, challenge_by_id[row.challenge_id]) for row in rows]
    return FusionAnalysisResponse(
        session_id=session.id,
        status=_overall_status(rows),
        fusion_version=get_settings().fusion_analysis_version,
        challenges=items,
        summary=_summary(items),
    )
