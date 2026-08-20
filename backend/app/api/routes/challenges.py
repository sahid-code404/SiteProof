import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.challenge import (
    ChallengeIssueResponse,
    ChallengeListResponse,
    ChallengeStartRequest,
    ChallengeSubmitRequest,
    ChallengeValidationResponse,
)
from app.services.challenges import (
    issue_next_challenge,
    list_challenges,
    start_challenge,
    submit_challenge,
)

router = APIRouter(tags=["verification-challenges"])


@router.post(
    "/sessions/{session_id}/challenges/next",
    response_model=ChallengeIssueResponse,
    summary="Issue the next unpredictable server-generated challenge",
)
def next_challenge(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChallengeIssueResponse:
    return issue_next_challenge(db, current_user, session_id)


@router.post(
    "/challenges/{challenge_id}/start",
    response_model=ChallengeIssueResponse,
    summary="Start the current challenge sensor window",
)
def begin_challenge(
    challenge_id: uuid.UUID,
    payload: ChallengeStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChallengeIssueResponse:
    return start_challenge(db, current_user, challenge_id, payload)


@router.post(
    "/challenges/{challenge_id}/submit",
    response_model=ChallengeValidationResponse,
    summary="Submit raw sensor evidence for authoritative server validation",
)
def validate_challenge(
    challenge_id: uuid.UUID,
    payload: ChallengeSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChallengeValidationResponse:
    return submit_challenge(db, current_user, challenge_id, payload)


@router.get(
    "/sessions/{session_id}/challenges",
    response_model=ChallengeListResponse,
    summary="List challenge attempts and explainable sensor-derived results",
)
def challenge_timeline(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChallengeListResponse:
    return list_challenges(db, current_user, session_id)
