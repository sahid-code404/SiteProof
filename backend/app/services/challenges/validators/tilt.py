from typing import Any

from app.core.config import Settings
from app.models.challenge import ChallengeType, VerificationChallenge
from app.schemas.challenge import ChallengeSubmitRequest
from app.services.challenges.validators.base import ChallengeValidationResult
from app.services.challenges.validators.motion_math import AxisMotionSpec, validate_axis_motion


class TiltChallengeValidator:
    def validate(
        self,
        challenge: VerificationChallenge,
        payload: ChallengeSubmitRequest,
        *,
        capabilities: dict[str, Any],
        settings: Settings,
    ) -> ChallengeValidationResult:
        sign = settings.tilt_down_sign
        if challenge.challenge_type == ChallengeType.TILT_UP:
            sign *= -1.0
        return validate_axis_motion(
            challenge,
            payload,
            spec=AxisMotionSpec(axis_index=0, expected_sign=sign, label="Tilt"),
            capabilities=capabilities,
            settings=settings,
        )
