import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.verification_engine import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    VerificationRecalculateRequest,
    VerificationResponse,
)
from app.services.verification.service import (
    create_review_decision,
    get_verification_response,
)
from app.services.verification.tasks import run_verification_task

router = APIRouter(tags=["verification"])


@router.get(
    "/sessions/{session_id}/verification",
    response_model=VerificationResponse,
)
def verification_result(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationResponse:
    return get_verification_response(db, current_user, session_id)


@router.post(
    "/sessions/{session_id}/verification/recalculate",
    response_model=VerificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def recalculate_verification(
    session_id: uuid.UUID,
    payload: VerificationRecalculateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> VerificationResponse:
    response = get_verification_response(db, current_user, session_id)
    background_tasks.add_task(
        run_verification_task,
        session_id,
        force=True,
        policy_version=payload.policy_version,
    )
    return response


@router.post(
    "/inspections/{inspection_id}/review",
    response_model=ReviewDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def review_inspection(
    inspection_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> ReviewDecisionResponse:
    return create_review_decision(
        db,
        current_user,
        inspection_id=inspection_id,
        session_id=payload.session_id,
        decision=payload.decision,
        reason=payload.reason,
    )
