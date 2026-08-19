import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.trust import (
    ReviewDecisionType,
    VerificationProcessingStatus,
    VerificationSignalStatus,
    VerificationSignalType,
    VerificationVerdict,
)
from app.schemas.base import APIModel


class VerificationPolicyInfo(APIModel):
    id: uuid.UUID
    name: str
    version: str


class VerificationSignalItem(APIModel):
    type: VerificationSignalType
    status: VerificationSignalStatus
    score: float
    confidence: float
    configured_weight: float
    effective_weight: float
    contribution: float
    required: bool
    reason_summary: str
    reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    source_algorithm_version: str | None = None


class ReviewDecisionItem(APIModel):
    id: uuid.UUID
    decision: ReviewDecisionType
    reason: str
    reviewer_user_id: uuid.UUID
    created_at: datetime


class VerificationResponse(APIModel):
    session_id: uuid.UUID
    inspection_id: uuid.UUID
    status: VerificationProcessingStatus
    score: float | None = None
    raw_score: float | None = None
    confidence: float | None = None
    verdict: VerificationVerdict | None = None
    policy: VerificationPolicyInfo | None = None
    engine_version: str | None = None
    calculation_revision: int | None = None
    signals: list[VerificationSignalItem] = Field(default_factory=list)
    hard_rules: list[str] = Field(default_factory=list)
    summary: str | None = None
    summary_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    latest_review: ReviewDecisionItem | None = None
    detailed: bool = False
    calculated_at: datetime | None = None


class VerificationRecalculateRequest(APIModel):
    policy_version: str | None = Field(default=None, max_length=40)


class ReviewDecisionRequest(APIModel):
    session_id: uuid.UUID
    decision: ReviewDecisionType
    reason: str = Field(min_length=3, max_length=2000)


class ReviewDecisionResponse(APIModel):
    id: uuid.UUID
    inspection_id: uuid.UUID
    session_id: uuid.UUID
    verification_result_id: uuid.UUID
    reviewer_user_id: uuid.UUID
    decision: ReviewDecisionType
    reason: str
    created_at: datetime
