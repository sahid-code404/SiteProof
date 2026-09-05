import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.semantic_challenge import SemanticChallengeStatus, SemanticChallengeType
from app.schemas.base import APIModel


class SemanticChallengeStartRequest(APIModel):
    nonce: str = Field(min_length=16, max_length=128)
    client_monotonic_ns: int = Field(ge=0)


class SemanticChallengeCompleteRequest(APIModel):
    nonce: str = Field(min_length=16, max_length=128)
    client_monotonic_ns: int = Field(ge=0)


class SemanticChallengeIssueResponse(APIModel):
    challenge_id: uuid.UUID
    sequence_number: int
    total_challenges: int
    type: SemanticChallengeType
    instruction: str
    target: dict[str, Any]
    issued_at: datetime
    expires_at: datetime
    server_time: datetime
    nonce: str


class SemanticChallengeCompleteResponse(APIModel):
    challenge_id: uuid.UUID
    sequence_number: int
    type: SemanticChallengeType
    status: SemanticChallengeStatus
    window_start_ms: int
    window_end_ms: int
    sequence_complete: bool
    server_time: datetime


class SemanticChallengeTimelineItem(APIModel):
    id: uuid.UUID
    sequence_number: int
    type: SemanticChallengeType
    instruction: str
    target: dict[str, Any]
    status: SemanticChallengeStatus
    issued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime
    window_start_ms: int | None = None
    window_end_ms: int | None = None


class SemanticChallengeListResponse(APIModel):
    session_id: uuid.UUID
    total_required: int
    sequence_complete: bool
    items: list[SemanticChallengeTimelineItem]
