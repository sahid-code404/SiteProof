import uuid
from typing import Any

from pydantic import Field

from app.models.challenge import ChallengeType
from app.models.visual_motion import VisualAnalysisStatus, VisualDirection, VisualQuality
from app.schemas.base import APIModel


class VisualChallengeAnalysisItem(APIModel):
    challenge_id: uuid.UUID
    challenge_type: ChallengeType
    analysis_version: str
    status: VisualAnalysisStatus
    visual_direction: VisualDirection
    estimated_rotation_degrees: float | None = None
    translation_x: float | None = None
    translation_y: float | None = None
    scale_change: float | None = None
    motion_start_ms: int | None = None
    motion_end_ms: int | None = None
    feature_count: int = 0
    tracked_feature_count: int = 0
    inlier_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    scene_continuity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    duplicate_frame_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    freeze_duration_ms: int = 0
    invalid_frame_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    visual_quality: VisualQuality
    reasons: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class VisualAnalysisResponse(APIModel):
    session_id: uuid.UUID
    status: VisualAnalysisStatus
    analysis_version: str
    challenges: list[VisualChallengeAnalysisItem]
