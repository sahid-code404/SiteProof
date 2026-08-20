from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings
from app.models.challenge import ChallengeResult, VerificationChallenge
from app.schemas.challenge import ChallengeSubmitRequest


@dataclass(frozen=True)
class ChallengeValidationResult:
    result: ChallengeResult
    score: float
    sensor_score: float
    reasons: list[str]
    metrics: dict[str, Any]
    sensor_quality: dict[str, Any]
    failure_reason: str | None = None


class ChallengeValidator(Protocol):
    def validate(
        self,
        challenge: VerificationChallenge,
        payload: ChallengeSubmitRequest,
        *,
        capabilities: dict[str, Any],
        settings: Settings,
    ) -> ChallengeValidationResult: ...
