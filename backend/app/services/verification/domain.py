from dataclasses import dataclass, field
from typing import Any

from app.models.trust import VerificationSignalStatus, VerificationSignalType


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class VerificationSignal:
    type: VerificationSignalType
    status: VerificationSignalStatus
    score: float
    confidence: float
    available: bool
    required: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    source_algorithm_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", clamp01(self.score))
        object.__setattr__(self, "confidence", clamp01(self.confidence))


@dataclass(frozen=True)
class HardRuleFinding:
    code: str
    severity: str
    message: str
