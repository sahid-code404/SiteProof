import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.core.errors import SiteProofError
from app.db.session import get_db
from app.models.trust import VerificationProcessingStatus, VerificationVerdict
from app.models.user import User, UserRole
from app.models.verification import VerificationSession
from app.schemas.verification_result import (
    ReviewDecisionResponse,
    ReviewQueueResponse,
    ReviewRequest,
    VerificationPolicySummary,
    VerificationResponse,
    VerificationSignalItem,
)
from app.services.audit_service import record_audit
from app.services.session_common import viewable_session
from app.services.verification.queue import list_review_queue
from app.services.verification.review import create_review_decision, latest_review_for_result
from app.services.verification.service import (
    ENGINE_VERSION,
    calculate_verification,
    get_scoped_result,
    signal_rows,
)

router = APIRouter(tags=["verification"])


def _response(
    db: Session,
    current_user: User,
    session: VerificationSession,
) -> VerificationResponse:
    result = get_scoped_result(db, current_user, session.id)
    if result is None:
        return VerificationResponse(
            session_id=session.id,
            inspection_id=session.inspection_id,
            status=VerificationProcessingStatus.PENDING,
        )
    detailed = current_user.role in {UserRole.ADMIN, UserRole.REVIEWER}
    signals = []
    if detailed:
        signals = [
            VerificationSignalItem(
                type=row.signal_type,
                status=row.status,
                score=row.score,
                confidence=row.confidence,
                weight=row.weight,
                contribution=row.weighted_contribution,
                required=row.required,
                reason_summary=row.reason_summary,
                reasons=row.reasons_json or [],
                metrics=row.metrics_json or {},
                source_algorithm_version=row.source_algorithm_version,
            )
            for row in signal_rows(db, result.id)
        ]
    review = latest_review_for_result(db, result.id) if detailed else None
    return VerificationResponse(
        result_id=result.id,
        session_id=result.session_id,
        inspection_id=result.inspection_id,
        status=result.processing_status,
        score=result.final_score,
        confidence=result.overall_confidence,
        verdict=result.verdict,
        policy=VerificationPolicySummary(
            id=result.policy_id,
            name=result.policy_name,
            version=result.policy_version,
            engine_version=result.engine_version,
        ),
        signals=signals,
        hard_rules=(result.hard_rule_codes_json or []) if detailed else [],
        summary=result.summary,
        summary_reasons=(result.summary_reasons_json or []) if detailed else [],
        warnings=(result.warnings_json or []) if detailed else [],
        limitations=(result.limitations_json or []) if detailed else [],
        calculated_at=result.calculated_at,
        latest_review=(
            ReviewDecisionResponse(
                id=review.id,
                decision=review.decision,
                reason=review.reason,
                reviewer_user_id=review.reviewer_user_id,
                created_at=review.created_at,
            )
            if review is not None
            else None
        ),
    )


@router.get("/review-queue", response_model=ReviewQueueResponse)
def review_queue(
    search: str | None = Query(default=None, max_length=200),
    inspector: str | None = Query(default=None, max_length=200),
    verdict: VerificationVerdict | None = None,
    reviewed: bool | None = None,
    date_from: datetime | None = Query(default=None, alias="dateFrom"),
    date_to: datetime | None = Query(default=None, alias="dateTo"),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> ReviewQueueResponse:
    return list_review_queue(
        db,
        current_user,
        search=search,
        inspector=inspector,
        verdict=verdict,
        reviewed=reviewed,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


@router.get(
    "/sessions/{session_id}/verification",
    response_model=VerificationResponse,
)
def verification_result(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationResponse:
    session = viewable_session(db, current_user, session_id)
    return _response(db, current_user, session)


@router.post(
    "/sessions/{session_id}/verification/recalculate",
    response_model=VerificationResponse,
)
def recalculate_verification(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> VerificationResponse:
    session = db.get(VerificationSession, session_id)
    if session is None or session.organization_id != current_user.organization_id:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")
    result = calculate_verification(
        db,
        session.id,
        actor_user_id=current_user.id,
        force=True,
    )
    if result.engine_version != ENGINE_VERSION:
        raise SiteProofError(
            409,
            "ENGINE_VERSION_CONFLICT",
            "Verification engine version changed.",
        )
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_RESULT",
        entity_id=result.id,
        action="VERIFICATION_RECALCULATED",
        metadata={
            "engineVersion": result.engine_version,
            "policyVersion": result.policy_version,
            "score": result.final_score,
            "verdict": result.verdict.value if result.verdict else None,
        },
    )
    db.commit()
    return _response(db, current_user, session)


@router.post(
    "/inspections/{inspection_id}/review",
    response_model=ReviewDecisionResponse,
)
def review_inspection(
    inspection_id: uuid.UUID,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> ReviewDecisionResponse:
    decision = create_review_decision(db, current_user, inspection_id, payload)
    return ReviewDecisionResponse(
        id=decision.id,
        decision=decision.decision,
        reason=decision.reason,
        reviewer_user_id=decision.reviewer_user_id,
        created_at=decision.created_at,
    )