import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.semantic_challenge import (
    SemanticChallengeCompleteRequest,
    SemanticChallengeCompleteResponse,
    SemanticChallengeIssueResponse,
    SemanticChallengeListResponse,
    SemanticChallengeStartRequest,
)
from app.services.semantic_challenges import (
    complete_semantic_challenge,
    issue_next_semantic_challenge,
    list_semantic_challenges,
    start_semantic_challenge,
)

router = APIRouter(tags=["semantic-capture-challenges"])


@router.post(
    "/sessions/{session_id}/semantic-challenges/next",
    response_model=SemanticChallengeIssueResponse,
    summary="Issue the next unpredictable assignment-specific visual proof challenge",
)
def next_semantic_challenge(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SemanticChallengeIssueResponse:
    return issue_next_semantic_challenge(db, current_user, session_id)


@router.post(
    "/semantic-challenges/{challenge_id}/start",
    response_model=SemanticChallengeIssueResponse,
    summary="Bind a semantic proof challenge to the active monotonic capture timeline",
)
def begin_semantic_challenge(
    challenge_id: uuid.UUID,
    payload: SemanticChallengeStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SemanticChallengeIssueResponse:
    return start_semantic_challenge(db, current_user, challenge_id, payload)


@router.post(
    "/semantic-challenges/{challenge_id}/complete",
    response_model=SemanticChallengeCompleteResponse,
    summary="Close the semantic proof evidence window without trusting a client verdict",
)
def finish_semantic_challenge(
    challenge_id: uuid.UUID,
    payload: SemanticChallengeCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SemanticChallengeCompleteResponse:
    return complete_semantic_challenge(db, current_user, challenge_id, payload)


@router.get(
    "/sessions/{session_id}/semantic-challenges",
    response_model=SemanticChallengeListResponse,
    summary="List semantic challenge attempts and capture-window bindings",
)
def semantic_challenge_timeline(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SemanticChallengeListResponse:
    return list_semantic_challenges(db, current_user, session_id)
