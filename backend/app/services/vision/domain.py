from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.models.visual_motion import VisualAnalysisStatus, VisualDirection, VisualQuality


@dataclass(frozen=True)
class VideoMetadata:
    codec: str
    width: int
    height: int
    fps: float
    duration_ms: int
    frame_count: int


@dataclass(frozen=True)
class VisualFrame:
    frame_index: int
    video_time_ms: int
    session_time_ms: int
    image: np.ndarray


@dataclass(frozen=True)
class MotionEstimate:
    timestamp_ms: int
    rotation_degrees: float
    translation_x: float
    translation_y: float
    scale: float
    tracked_points: int
    inliers: int
    inlier_ratio: float
    median_flow_px: float
    feature_coverage: float
    homography_inlier_ratio: float | None = None


@dataclass(frozen=True)
class ContinuityMetrics:
    score: float
    scene_cut_detected: bool
    scene_cut_count: int
    duplicate_frame_ratio: float
    freeze_duration_ms: int
    invalid_frame_ratio: float
    black_frame_ratio: float
    mean_brightness: float
    mean_sharpness: float


@dataclass(frozen=True)
class AnalysisOutcome:
    status: VisualAnalysisStatus
    direction: VisualDirection
    quality: VisualQuality
    estimated_rotation_degrees: float | None
    translation_x: float | None
    translation_y: float | None
    scale_change: float | None
    motion_start_ms: int | None
    motion_end_ms: int | None
    feature_count: int
    tracked_feature_count: int
    inlier_ratio: float
    confidence: float
    continuity: ContinuityMetrics
    reasons: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
