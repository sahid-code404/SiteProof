import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import SiteProofError
from app.models.trust import (
    ReviewDecision,
    ReviewDecisionType,
    VerificationPolicy,
    VerificationProcessingStatus,
    VerificationResult,
    VerificationSignalResult,
)
from app.models.user import User, UserRole
from app.models.verification import VerificationSession
from app.schemas.verification_engine import (
    ReviewDecisionItem,
    ReviewDecisionResponse,
    VerificationPolicyInfo,
    VerificationResponse,
    VerificationSignalItem,
)
from app.services.audit_service import record_audit
from app.services.session_common import viewable_session


def _scoped_session(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
) -> VerificationSession:
    if current_user.role == UserRole.INSPECTOR:
        return viewable_session(db, current_user, session_id)
    session = db.get(VerificationSession, session_id)
    if session is None or session.organization_id != current_user.organization_id:
        raise SiteProofError(
            404,
            "SESSION_NOT_FOUND",
            "Verification session was not found.",
        )
    return session


def latest_verification_result(
    db: Session,
    session_id: uuid.UUID,
) -> VerificationResult | None:
    return db.scalar(
        select(VerificationResult)
        .where(VerificationResult.session_id == session_id)
        .order_by(
            VerificationResult.created_at.desc(),
            VerificationResult.calculation_revision.desc(),
        )
    )


def _latest_review(db: Session, result_id: uuid.UUID) -> ReviewDecision | None:
    return db.scalar(
        select(ReviewDecision)
        .where(ReviewDecision.verification_result_id == result_id)
        .order_by(ReviewDecision.created_at.desc())
    )


def _review_item(row: ReviewDecision | None) -> ReviewDecisionItem | None:
    if row is None:
        return None
    return ReviewDecisionItem(
        id=row.id,
        decision=row.decision,
        reason=row.reason,
        reviewer_user_id=row.reviewer_user_id,
        created_at=row.created_at,
    )


def get_verification_response(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
) -> VerificationResponse:
    session = _scoped_session(db, current_user, session_id)
    result = latest_verification_result(db, session.id)
    if result is None:
        return VerificationResponse(
            session_id=session.id,
            inspection_id=session.inspection_id,
            status=VerificationProcessingStatus.PENDING,
            summary="Verification has not been calculated yet.",
            detailed=current_user.role in {UserRole.ADMIN, UserRole.REVIEWER},
        )

    policy = db.get(VerificationPolicy, result.policy_id)
    detailed = current_user.role in {UserRole.ADMIN, UserRole.REVIEWER}
    signal_items: list[VerificationSignalItem] = []
    if detailed:
        rows = list(
            db.scalars(
                select(VerificationSignalResult)
                .where(VerificationSignalResult.verification_result_id == result.id)
                .order_by(VerificationSignalResult.created_at)
            ).all()
        )
        signal_items = [
            VerificationSignalItem(
                type=row.signal_type,
                status=row.status,
                score=row.score,
                confidence=row.confidence,
                configured_weight=row.configured_weight,
                effective_weight=row.effective_weight,
                contribution=row.weighted_contribution,
                required=row.required,
                reason_summary=row.reason_summary,
                reasons=list(row.reasons_json or []),
                metrics=dict(row.metrics_json or {}),
                source_algorithm_version=row.source_algorithm_version,
            )
            for row in rows
        ]

    if detailed:
        score = result.final_score
        raw_score = result.raw_score
        confidence = result.overall_confidence
        hard_rules = list(result.hard_rule_codes_json or [])
        summary_reasons = list(result.summary_reasons_json or [])
        warnings = list(result.warnings_json or [])
        summary = result.summary
    else:
        score = None
        raw_score = None
        confidence = None
        hard_rules = []
        summary_reasons = []
        warnings = []
        if result.processing_status != VerificationProcessingStatus.COMPLETED:
            summary = "Verification is still being processed."
        elif result.verdict and result.verdict.value == "VERIFIED":
            summary = "Evidence accepted by automated checks."
        else:
            summary = "Verification is under review."

    return VerificationResponse(
        session_id=session.id,
        inspection_id=session.inspection_id,
        status=result.processing_status,
        score=score,
        raw_score=raw_score,
        confidence=confidence,
        verdict=result.verdict,
        policy=(
            VerificationPolicyInfo(
                id=policy.id,
                name=policy.name,
                version=policy.version,
            )
            if policy is not None
            else None
        ),
        engine_version=result.engine_version,
        calculation_revision=result.calculation_revision,
        signals=signal_items,
        hard_rules=hard_rules,
        summary=summary,
        summary_reasons=summary_reasons,
        warnings=warnings,
        latest_review=_review_item(_latest_review(db, result.id)) if detailed else None,
        detailed=detailed,
        calculated_at=result.calculated_at,
    )


def create_review_decision(
    db: Session,
    current_user: User,
    *,
    inspection_id: uuid.UUID,
    session_id: uuid.UUID,
    decision: ReviewDecisionType,
    reason: str,
) -> ReviewDecisionResponse:
    if current_user.role not in {UserRole.ADMIN, UserRole.REVIEWER}:
        raise SiteProofError(403, "FORBIDDEN", "Reviewer permission is required.")

    session = db.get(VerificationSession, session_id)
    if (
        session is None
        or session.organization_id != current_user.organization_id
        or session.inspection_id != inspection_id
    ):
        raise SiteProofError(
            404,
            "SESSION_NOT_FOUND",
            "Verification session was not found.",
        )

    result = latest_verification_result(db, session.id)
    if (
        result is None
        or result.processing_status != VerificationProcessingStatus.COMPLETED
    ):
        raise SiteProofError(
            409,
            "VERIFICATION_NOT_READY",
            "A completed automated verification result is required before review.",
        )

    row = ReviewDecision(
        organization_id=current_user.organization_id,
        inspection_id=inspection_id,
        session_id=session.id,
        verification_result_id=result.id,
        reviewer_user_id=current_user.id,
        decision=decision,
        reason=reason.strip(),
    )
    db.add(row)
    db.flush()
    action = {
        ReviewDecisionType.APPROVED: "REVIEW_APPROVED",
        ReviewDecisionType.REJECTED: "REVIEW_REJECTED",
        ReviewDecisionType.RECAPTURE_REQUIRED: "RECAPTURE_REQUESTED",
    }[decision]
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_RESULT",
        entity_id=result.id,
        action=action,
        metadata={
            "sessionId": str(session.id),
            "decision": decision.value,
            "verificationRevision": result.calculation_revision,
        },
    )
    db.commit()
    db.refresh(row)
    return ReviewDecisionResponse(
        id=row.id,
        inspection_id=row.inspection_id,
        session_id=row.session_id,
        verification_result_id=row.verification_result_id,
        reviewer_user_id=row.reviewer_user_id,
        decision=row.decision,
        reason=row.reason,
        created_at=row.created_at,
    )
