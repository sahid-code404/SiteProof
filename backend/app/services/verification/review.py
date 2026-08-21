import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import SiteProofError
from app.models.inspection import Inspection, InspectionStatus
from app.models.trust import ReviewDecision, ReviewDecisionType, VerificationResult
from app.models.user import User
from app.models.verification import VerificationSession
from app.schemas.verification_result import ReviewRequest
from app.services.audit_service import record_audit


def create_review_decision(
    db: Session,
    current_user: User,
    inspection_id: uuid.UUID,
    payload: ReviewRequest,
) -> ReviewDecision:
    inspection = db.scalar(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.organization_id == current_user.organization_id,
        )
    )
    if inspection is None:
        raise SiteProofError(404, "INSPECTION_NOT_FOUND", "Inspection was not found.")
    session = db.scalar(
        select(VerificationSession).where(
            VerificationSession.id == payload.session_id,
            VerificationSession.inspection_id == inspection.id,
            VerificationSession.organization_id == current_user.organization_id,
        )
    )
    if session is None:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")
    result = db.scalar(
        select(VerificationResult)
        .where(
            VerificationResult.session_id == session.id,
            VerificationResult.organization_id == current_user.organization_id,
        )
        .order_by(VerificationResult.created_at.desc())
    )
    if result is None or result.verdict is None:
        raise SiteProofError(
            409,
            "VERIFICATION_NOT_READY",
            "Automated verification must complete before human review.",
        )

    reason = payload.reason.strip()
    if payload.decision in {
        ReviewDecisionType.REJECTED,
        ReviewDecisionType.RECAPTURE_REQUIRED,
    } and len(reason) < 8:
        raise SiteProofError(
            422,
            "REVIEW_REASON_REQUIRED",
            "Rejection and recapture decisions require a meaningful reason.",
        )

    decision = ReviewDecision(
        organization_id=current_user.organization_id,
        inspection_id=inspection.id,
        session_id=session.id,
        verification_result_id=result.id,
        reviewer_user_id=current_user.id,
        decision=payload.decision,
        reason=reason,
    )
    db.add(decision)

    action = {
        ReviewDecisionType.APPROVED: "REVIEW_APPROVED",
        ReviewDecisionType.REJECTED: "REVIEW_REJECTED",
        ReviewDecisionType.RECAPTURE_REQUIRED: "RECAPTURE_REQUESTED",
    }[payload.decision]
    if payload.decision == ReviewDecisionType.APPROVED:
        inspection.status = InspectionStatus.APPROVED
    elif payload.decision == ReviewDecisionType.REJECTED:
        inspection.status = InspectionStatus.REJECTED
    else:
        inspection.status = InspectionStatus.RECAPTURE_REQUIRED

    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="INSPECTION",
        entity_id=inspection.id,
        action=action,
        metadata={
            "sessionId": str(session.id),
            "verificationResultId": str(result.id),
            "automatedVerdict": result.verdict.value,
            "decision": payload.decision.value,
        },
    )
    db.commit()
    db.refresh(decision)
    return decision


def latest_review_for_result(db: Session, result_id: uuid.UUID) -> ReviewDecision | None:
    return db.scalar(
        select(ReviewDecision)
        .where(ReviewDecision.verification_result_id == result_id)
        .order_by(ReviewDecision.created_at.desc())
    )
