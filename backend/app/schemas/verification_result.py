import uuid
from datetime import datetime

from pydantic import Field

from app.models.trust import (
    ReviewDecisionType,
    VerificationProcessingStatus,
    VerificationSignalStatus,
    VerificationSignalType,
    VerificationVerdict,
)
from app.schemas.base import APIModel


class VerificationPolicySummary(APIModel):
    id: uuid.UUID
    name: str
    version: str
    engine_version: str


class VerificationSignalItem(APIModel):
    type: VerificationSignalType
    status: VerificationSignalStatus
    score: float
    confidence: float
    weight: float
    contribution: float
    required: bool
    reason_summary: str
    reasons: list[str]
    metrics: dict
    source_algorithm_version: str | None = None


class ReviewDecisionResponse(APIModel):
    id: uuid.UUID
    decision: ReviewDecisionType
    reason: str
    reviewer_user_id: uuid.UUID
    created_at: datetime


class VerificationResponse(APIModel):
    result_id: uuid.UUID | None = None
    session_id: uuid.UUID
    inspection_id: uuid.UUID
    status: VerificationProcessingStatus
    score: float | None = None
    confidence: float | None = None
    verdict: VerificationVerdict | None = None
    policy: VerificationPolicySummary | None = None
    signals: list[VerificationSignalItem] = Field(default_factory=list)
    hard_rules: list[str] = Field(default_factory=list)
    summary: str | None = None
    summary_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    calculated_at: datetime | None = None
    latest_review: ReviewDecisionResponse | None = None


class ReviewRequest(APIModel):
    session_id: uuid.UUID
    decision: ReviewDecisionType
    reason: str = Field(default="", max_length=2000)
