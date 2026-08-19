import json
import logging
import tempfile
import time
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.db.session import SessionLocal
from app.models.challenge import VerificationChallenge
from app.models.user import User
from app.models.verification import EvidenceFile, EvidenceFileType, EvidenceUploadStatus, VerificationSession, VerificationSessionStatus
from app.models.visual_motion import VisualAnalysisStatus, VisualDirection, VisualMotionResult, VisualQuality
from app.schemas.visual_analysis import VisualAnalysisResponse, VisualChallengeAnalysisItem
from app.services.audit_service import record_audit
from app.services.storage_service import StorageService, get_storage_service
from app.services.vision.timeline import (
    challenge_metadata_by_id,
    map_challenge_window,
    validate_client_server_start_alignment,
    video_start_relative_ms,
)
from app.services.vision.video_reader import VideoDecodeError, inspect_video, sample_window
from app.services.vision.visual_challenge_analyzer import analyze_visual_challenge

logger = logging.getLogger("siteproof.vision")


def _evidence_records(db: Session, session_id: uuid.UUID) -> dict[EvidenceFileType, EvidenceFile]:
    return {
        item.file_type: item
        for item in db.scalars(select(EvidenceFile).where(EvidenceFile.session_id == session_id)).all()
    }


def _require_evidence(records: dict[EvidenceFileType, EvidenceFile], file_type: EvidenceFileType) -> EvidenceFile:
    record = records.get(file_type)
    if record is None or record.upload_status != EvidenceUploadStatus.UPLOADED or not record.hash_verified:
        raise VideoDecodeError(f"Required {file_type.value} evidence is unavailable or unverified")
    return record


def _load_metadata(storage: StorageService, record: EvidenceFile) -> dict:
    settings = get_settings()
    raw = storage.read_bytes(record.storage_key, max_bytes=settings.max_metadata_bytes)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VideoDecodeError("Session metadata is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise VideoDecodeError("Session metadata root must be an object")
    return value


def _upsert_result(
    db: Session,
    *,
    session: VerificationSession,
    challenge: VerificationChallenge,
    status: VisualAnalysisStatus,
    direction: VisualDirection = VisualDirection.NONE,
    quality: VisualQuality = VisualQuality.POOR,
    estimated_rotation_degrees: float | None = None,
    translation_x: float | None = None,
    translation_y: float | None = None,
    scale_change: float | None = None,
    motion_start_ms: int | None = None,
    motion_end_ms: int | None = None,
    feature_count: int = 0,
    tracked_feature_count: int = 0,
    inlier_ratio: float = 0.0,
    visual_confidence: float = 0.0,
    scene_continuity_score: float = 0.0,
    duplicate_frame_ratio: float = 0.0,
    freeze_duration_ms: int = 0,
    invalid_frame_ratio: float = 0.0,
    diagnostics: dict | None = None,
) -> VisualMotionResult:
    version = get_settings().vision_analysis_version
    result = db.scalar(
        select(VisualMotionResult).where(
            VisualMotionResult.challenge_id == challenge.id,
            VisualMotionResult.analysis_version == version,
        )
    )
    if result is None:
        result = VisualMotionResult(
            organization_id=session.organization_id,
            session_id=session.id,
            challenge_id=challenge.id,
            analysis_version=version,
            analysis_status=status,
            visual_direction=direction,
            visual_quality=quality,
        )
        db.add(result)
    result.analysis_status = status
    result.visual_direction = direction
    result.visual_quality = quality
    result.estimated_rotation_degrees = estimated_rotation_degrees
    result.translation_x = translation_x
    result.translation_y = translation_y
    result.scale_change = scale_change
    result.motion_start_ms = motion_start_ms
    result.motion_end_ms = motion_end_ms
    result.feature_count = feature_count
    result.tracked_feature_count = tracked_feature_count
    result.inlier_ratio = max(0.0, min(1.0, inlier_ratio))
    result.visual_confidence = max(0.0, min(1.0, visual_confidence))
    result.scene_continuity_score = max(0.0, min(1.0, scene_continuity_score))
    result.duplicate_frame_ratio = max(0.0, min(1.0, duplicate_frame_ratio))
    result.freeze_duration_ms = max(0, freeze_duration_ms)
    result.invalid_frame_ratio = max(0.0, min(1.0, invalid_frame_ratio))
    result.diagnostics_json = diagnostics or {}
    return result


def _mark_failure(
    db: Session,
    *,
    session: VerificationSession,
    challenges: list[VerificationChallenge],
    message: str,
    temporary: bool,
) -> None:
    for challenge in challenges:
        _upsert_result(
            db,
            session=session,
            challenge=challenge,
            status=VisualAnalysisStatus.FAILED,
            diagnostics={
                "reasons": [message],
                "temporaryFailure": temporary,
            },
        )
        record_audit(
            db,
            organization_id=session.organization_id,
            actor_user_id=session.created_by_user_id,
            entity_type="VERIFICATION_CHALLENGE",
            entity_id=challenge.id,
            action="VISUAL_ANALYSIS_FAILED",
            metadata={"analysisVersion": get_settings().vision_analysis_version, "temporary": temporary},
        )
    db.commit()


def analyze_session_visual_motion(
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
    if session.status not in {VerificationSessionStatus.UPLOADED, VerificationSessionStatus.PROCESSING}:
        raise ValueError("Visual analysis requires a fully uploaded verification session")

    challenges = list(
        db.scalars(
            select(VerificationChallenge)
            .where(VerificationChallenge.session_id == session.id)
            .order_by(VerificationChallenge.sequence_number, VerificationChallenge.attempt_number)
        ).all()
    )
    if not challenges:
        raise ValueError("Visual analysis requires at least one recorded challenge")

    existing = list(
        db.scalars(
            select(VisualMotionResult).where(
                VisualMotionResult.session_id == session.id,
                VisualMotionResult.analysis_version == settings.vision_analysis_version,
            )
        ).all()
    )
    terminal = {VisualAnalysisStatus.SUCCESS, VisualAnalysisStatus.INCONCLUSIVE}
    if not force and len(existing) == len(challenges) and all(item.analysis_status in terminal for item in existing):
        return

    session.status = VerificationSessionStatus.PROCESSING
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=session.created_by_user_id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="VISUAL_ANALYSIS_STARTED",
        metadata={"analysisVersion": settings.vision_analysis_version},
    )
    for challenge in challenges:
        _upsert_result(
            db,
            session=session,
            challenge=challenge,
            status=VisualAnalysisStatus.PROCESSING,
        )
    db.commit()

    object_storage = storage or get_storage_service()
    records = _evidence_records(db, session.id)
    video_record = _require_evidence(records, EvidenceFileType.VIDEO)
    metadata_record = _require_evidence(records, EvidenceFileType.SESSION_METADATA)
    metadata = _load_metadata(object_storage, metadata_record)
    metadata_challenges = challenge_metadata_by_id(metadata)

    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="siteproof-vision-") as temp_dir:
            video_path = Path(temp_dir) / "capture.mp4"
            copied = object_storage.copy_to_file(video_record.storage_key, video_path)
            if copied.size_bytes != video_record.size_bytes:
                raise VideoDecodeError("Materialized video size does not match stored evidence metadata")

            video_metadata = inspect_video(video_path, settings)
            client_duration = int((metadata.get("capture") or {}).get("durationMs") or 0)
            if client_duration > 0:
                duration_tolerance = max(
                    settings.vision_timeline_tolerance_ms,
                    int(round(3.0 / video_metadata.fps * 1000.0)),
                )
                if abs(video_metadata.duration_ms - client_duration) > duration_tolerance:
                    raise VideoDecodeError(
                        "Decoded video duration does not agree with client capture metadata"
                    )

            video_offset_ms = video_start_relative_ms(metadata)
            for challenge in challenges:
                if time.monotonic() - started > settings.vision_max_processing_seconds:
                    raise TimeoutError("Visual analysis exceeded the configured processing limit")

                item = metadata_challenges.get(str(challenge.id))
                if item is None:
                    raise ValueError(f"Challenge {challenge.id} is absent from client evidence metadata")
                started_relative_ms = int(
                    item.get("startedRelativeMs", item.get("issuedRelativeMs", -1))
                )
                alignment_difference_ms = validate_client_server_start_alignment(
                    capture_anchor_monotonic_ns=session.capture_anchor_monotonic_ns,
                    challenge_client_start_monotonic_ns=challenge.client_start_monotonic_ns,
                    challenge_started_relative_ms=started_relative_ms,
                    tolerance_ms=settings.vision_timeline_tolerance_ms,
                )
                window = map_challenge_window(
                    metadata,
                    challenge_id=str(challenge.id),
                    challenge_type=challenge.challenge_type.value,
                    pre_padding_ms=settings.vision_pre_challenge_padding_ms,
                    post_padding_ms=settings.vision_post_challenge_padding_ms,
                    video_duration_ms=video_metadata.duration_ms,
                )
                frames, invalid_ratio = sample_window(
                    video_path,
                    metadata=video_metadata,
                    start_ms=window.video_start_ms,
                    end_ms=window.video_end_ms,
                    video_start_relative_ms=video_offset_ms,
                    settings=settings,
                )
                outcome = analyze_visual_challenge(
                    frames,
                    challenge_type=challenge.challenge_type,
                    invalid_frame_ratio=invalid_ratio,
                    settings=settings,
                )
                diagnostics = dict(outcome.diagnostics)
                diagnostics.update(
                    {
                        "reasons": outcome.reasons,
                        "video": {
                            "codec": video_metadata.codec,
                            "width": video_metadata.width,
                            "height": video_metadata.height,
                            "fps": round(video_metadata.fps, 4),
                            "durationMs": video_metadata.duration_ms,
                            "frameCount": video_metadata.frame_count,
                        },
                        "timeline": {
                            "videoStartRelativeMs": video_offset_ms,
                            "challengeStartSessionMs": window.challenge_start_session_ms,
                            "challengeEndSessionMs": window.challenge_end_session_ms,
                            "analysisVideoStartMs": window.video_start_ms,
                            "analysisVideoEndMs": window.video_end_ms,
                            "clientServerStartDifferenceMs": alignment_difference_ms,
                        },
                        "sampledFrames": len(frames),
                    }
                )
                _upsert_result(
                    db,
                    session=session,
                    challenge=challenge,
                    status=outcome.status,
                    direction=outcome.direction,
                    quality=outcome.quality,
                    estimated_rotation_degrees=outcome.estimated_rotation_degrees,
                    translation_x=outcome.translation_x,
                    translation_y=outcome.translation_y,
                    scale_change=outcome.scale_change,
                    motion_start_ms=outcome.motion_start_ms,
                    motion_end_ms=outcome.motion_end_ms,
                    feature_count=outcome.feature_count,
                    tracked_feature_count=outcome.tracked_feature_count,
                    inlier_ratio=outcome.inlier_ratio,
                    visual_confidence=outcome.confidence,
                    scene_continuity_score=outcome.continuity.score,
                    duplicate_frame_ratio=outcome.continuity.duplicate_frame_ratio,
                    freeze_duration_ms=outcome.continuity.freeze_duration_ms,
                    invalid_frame_ratio=outcome.continuity.invalid_frame_ratio,
                    diagnostics=diagnostics,
                )
                action = (
                    "VISUAL_ANALYSIS_COMPLETED"
                    if outcome.status == VisualAnalysisStatus.SUCCESS
                    else "VISUAL_ANALYSIS_INCONCLUSIVE"
                )
                record_audit(
                    db,
                    organization_id=session.organization_id,
                    actor_user_id=session.created_by_user_id,
                    entity_type="VERIFICATION_CHALLENGE",
                    entity_id=challenge.id,
                    action=action,
                    metadata={
                        "analysisVersion": settings.vision_analysis_version,
                        "status": outcome.status.value,
                        "confidence": round(outcome.confidence, 4),
                    },
                )
                db.commit()
    except (VideoDecodeError, ValueError) as exc:
        _mark_failure(
            db,
            session=session,
            challenges=challenges,
            message=str(exc),
            temporary=False,
        )
        raise
    except (TimeoutError, OSError) as exc:
        _mark_failure(
            db,
            session=session,
            challenges=challenges,
            message=str(exc),
            temporary=True,
        )
        raise


def run_visual_analysis_task(session_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        analyze_session_visual_motion(db, session_id)
    except Exception:
        logger.exception("visual analysis failed for session %s", session_id)
    finally:
        db.close()


def _overall_status(items: list[VisualMotionResult]) -> VisualAnalysisStatus:
    if not items:
        return VisualAnalysisStatus.PENDING
    statuses = {item.analysis_status for item in items}
    if VisualAnalysisStatus.PROCESSING in statuses or VisualAnalysisStatus.PENDING in statuses:
        return VisualAnalysisStatus.PROCESSING
    if VisualAnalysisStatus.FAILED in statuses:
        return VisualAnalysisStatus.FAILED
    if VisualAnalysisStatus.INCONCLUSIVE in statuses:
        return VisualAnalysisStatus.INCONCLUSIVE
    return VisualAnalysisStatus.SUCCESS


def get_visual_analysis(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
) -> VisualAnalysisResponse:
    session = db.get(VerificationSession, session_id)
    if session is None or session.organization_id != current_user.organization_id:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")

    challenges = {
        item.id: item
        for item in db.scalars(
            select(VerificationChallenge).where(VerificationChallenge.session_id == session.id)
        ).all()
    }
    results = list(
        db.scalars(
            select(VisualMotionResult)
            .where(
                VisualMotionResult.session_id == session.id,
                VisualMotionResult.analysis_version == get_settings().vision_analysis_version,
            )
            .order_by(VisualMotionResult.created_at)
        ).all()
    )
    items: list[VisualChallengeAnalysisItem] = []
    for result in results:
        challenge = challenges.get(result.challenge_id)
        if challenge is None:
            continue
        diagnostics = result.diagnostics_json or {}
        items.append(
            VisualChallengeAnalysisItem(
                challenge_id=challenge.id,
                challenge_type=challenge.challenge_type,
                analysis_version=result.analysis_version,
                status=result.analysis_status,
                visual_direction=result.visual_direction,
                estimated_rotation_degrees=result.estimated_rotation_degrees,
                translation_x=result.translation_x,
                translation_y=result.translation_y,
                scale_change=result.scale_change,
                motion_start_ms=result.motion_start_ms,
                motion_end_ms=result.motion_end_ms,
                feature_count=result.feature_count,
                tracked_feature_count=result.tracked_feature_count,
                inlier_ratio=result.inlier_ratio,
                confidence=result.visual_confidence,
                scene_continuity_score=result.scene_continuity_score,
                duplicate_frame_ratio=result.duplicate_frame_ratio,
                freeze_duration_ms=result.freeze_duration_ms,
                invalid_frame_ratio=result.invalid_frame_ratio,
                visual_quality=result.visual_quality,
                reasons=list(diagnostics.get("reasons") or []),
                diagnostics=diagnostics,
            )
        )
    return VisualAnalysisResponse(
        session_id=session.id,
        status=_overall_status(results),
        analysis_version=get_settings().vision_analysis_version,
        challenges=items,
    )
