from dataclasses import dataclass, field
from typing import Any

from app.models.trust import (
    VerificationSignalStatus,
    VerificationSignalType,
    VerificationVerdict,
)


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
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Verification signal score must be between 0 and 1")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Verification signal confidence must be between 0 and 1")


@dataclass(frozen=True)
class PolicyDefinition:
    name: str
    version: str
    verified_threshold: float
    review_threshold: float
    minimum_required_confidence: float
    weights: dict[VerificationSignalType, float]
    required_signals: frozenset[VerificationSignalType]
    hard_rules: frozenset[str]


@dataclass(frozen=True)
class HardRuleResult:
    code: str
    maximum_verdict: VerificationVerdict
    explanation: str


@dataclass(frozen=True)
class ScoreBreakdown:
    raw_score: float
    overall_confidence: float
    contributions: dict[VerificationSignalType, float]
    available_weight: float


@dataclass(frozen=True)
class EngineDecision:
    score: float
    confidence: float
    verdict: VerificationVerdict
    hard_rules: list[HardRuleResult]
    summary_reasons: list[str]
    warnings: list[str]
