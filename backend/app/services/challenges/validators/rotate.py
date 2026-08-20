from typing import Any

from app.core.config import Settings
from app.models.challenge import ChallengeType, VerificationChallenge
from app.schemas.challenge import ChallengeSubmitRequest
from app.services.challenges.validators.base import ChallengeValidationResult
from app.services.challenges.validators.motion_math import AxisMotionSpec, validate_axis_motion


class RotateChallengeValidator:
    def validate(
        self,
        challenge: VerificationChallenge,
        payload: ChallengeSubmitRequest,
        *,
        capabilities: dict[str, Any],
        settings: Settings,
    ) -> ChallengeValidationResult:
        sign = settings.rotation_right_sign
        if challenge.challenge_type == ChallengeType.ROTATE_LEFT:
            sign *= -1.0
        return validate_axis_motion(
            challenge,
            payload,
            spec=AxisMotionSpec(axis_index=1, expected_sign=sign, label="Rotation"),
            capabilities=capabilities,
            settings=settings,
        )
