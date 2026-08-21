import uuid
from typing import Any

from pydantic import Field

from app.models.challenge import ChallengeType
from app.models.fusion import (
    ConsistencyStatus,
    FusionAnalysisStatus,
    MismatchReason,
    MotionDirection,
)
from app.schemas.base import APIModel


class FusionCurvePoint(APIModel):
    time_ms: int
    value: float = Field(ge=0.0, le=1.0)


class FusionChallengeAnalysisItem(APIModel):
    challenge_id: uuid.UUID
    challenge_type: ChallengeType
    fusion_version: str
    analysis_status: FusionAnalysisStatus
    consistency_status: ConsistencyStatus

    sensor_direction: MotionDirection
    visual_direction: MotionDirection
    sensor_angle_deg: float | None = None
    visual_angle_deg: float | None = None
    angle_difference_deg: float | None = None
    relative_angle_error: float | None = None

    sensor_start_ms: int | None = None
    visual_start_ms: int | None = None
    start_offset_ms: int | None = None
    sensor_peak_ms: int | None = None
    visual_peak_ms: int | None = None
    sensor_end_ms: int | None = None
    visual_end_ms: int | None = None
    end_offset_ms: int | None = None
    sensor_duration_ms: int | None = None
    visual_duration_ms: int | None = None

    motion_curve_correlation: float | None = Field(default=None, ge=-1.0, le=1.0)
    best_lag_ms: int | None = None

    direction_score: float | None = Field(default=None, ge=0.0, le=1.0)
    magnitude_score: float | None = Field(default=None, ge=0.0, le=1.0)
    timing_score: float | None = Field(default=None, ge=0.0, le=1.0)
    duration_score: float | None = Field(default=None, ge=0.0, le=1.0)
    correlation_score: float | None = Field(default=None, ge=0.0, le=1.0)
    raw_consistency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    consistency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    fusion_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    sensor_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    visual_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    mismatch_reasons: list[MismatchReason] = Field(default_factory=list)
    explanations: list[str] = Field(default_factory=list)
    sensor_curve: list[FusionCurvePoint] = Field(default_factory=list)
    visual_curve: list[FusionCurvePoint] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class FusionSessionSummary(APIModel):
    challenge_count: int = 0
    consistent: int = 0
    partially_consistent: int = 0
    mismatch: int = 0
    inconclusive: int = 0
    mean_consistency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    strong_contradiction_detected: bool = False


class FusionAnalysisResponse(APIModel):
    session_id: uuid.UUID
    status: FusionAnalysisStatus
    fusion_version: str
    challenges: list[FusionChallengeAnalysisItem]
    summary: FusionSessionSummary
