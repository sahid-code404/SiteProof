from dataclasses import dataclass, field
from enum import Enum


class MotionSource(str, Enum):
    SENSOR = "SENSOR"
    VISION = "VISION"


class MotionKind(str, Enum):
    ROTATION = "ROTATION"
    TILT = "TILT"


@dataclass(frozen=True)
class MotionCurvePoint:
    time_ms: int
    value: float


@dataclass(frozen=True)
class MotionEstimate:
    direction: str
    angular_change_deg: float | None
    start_ms: int | None
    peak_ms: int | None
    end_ms: int | None
    confidence: float
    source: MotionSource
    quality: str
    kind: MotionKind
    curve: tuple[MotionCurvePoint, ...] = ()

    @property
    def duration_ms(self) -> int | None:
        if self.start_ms is None or self.end_ms is None:
            return None
        return max(0, self.end_ms - self.start_ms)


@dataclass(frozen=True)
class CurveComparison:
    pearson_correlation: float | None
    best_correlation: float | None
    best_lag_ms: int | None
    sensor_curve: tuple[MotionCurvePoint, ...] = ()
    visual_curve: tuple[MotionCurvePoint, ...] = ()


@dataclass(frozen=True)
class FusionDecision:
    consistency_status: str
    raw_consistency_score: float | None
    effective_consistency_score: float | None
    fusion_confidence: float
    mismatch_reasons: tuple[str, ...] = ()
    explanations: tuple[str, ...] = ()
    diagnostics: dict = field(default_factory=dict)
