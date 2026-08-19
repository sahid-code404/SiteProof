import secrets
from dataclasses import dataclass
from random import SystemRandom

from app.core.config import Settings
from app.models.challenge import ChallengeType

_rng = SystemRandom()


@dataclass(frozen=True)
class ChallengeDefinition:
    challenge_type: ChallengeType
    parameters: dict[str, float]
    instruction: str
    nonce: str


def instruction_for(challenge_type: ChallengeType) -> str:
    return {
        ChallengeType.ROTATE_LEFT: "Rotate your phone to the left.",
        ChallengeType.ROTATE_RIGHT: "Rotate your phone to the right.",
        ChallengeType.TILT_UP: "Tilt the top of your phone upward.",
        ChallengeType.TILT_DOWN: "Tilt the top of your phone downward.",
    }[challenge_type]


def _comfortable_parameters(target: float, minimum_floor: float, maximum_ceiling: float) -> dict[str, float]:
    tolerance_low = _rng.uniform(9.0, 13.0)
    tolerance_high = _rng.uniform(10.0, 15.0)
    minimum = max(minimum_floor, target - tolerance_low)
    maximum = min(maximum_ceiling, target + tolerance_high)
    return {
        "targetDegrees": round(target, 1),
        "minDegrees": round(minimum, 1),
        "maxDegrees": round(maximum, 1),
    }


def generate_definition(
    *,
    sequence_number: int,
    previous_type: ChallengeType | None,
    settings: Settings,
) -> ChallengeDefinition:
    # A rotation/tilt/rotation cadence keeps the phone comfortable while each direction,
    # target and nonce remains server-selected and unknown before issuance.
    if sequence_number % 2 == 0:
        candidates = [ChallengeType.TILT_UP, ChallengeType.TILT_DOWN]
        target = _rng.uniform(settings.tilt_min_target_degrees, settings.tilt_max_target_degrees)
        parameters = _comfortable_parameters(target, 12.0, 60.0)
    else:
        candidates = [ChallengeType.ROTATE_LEFT, ChallengeType.ROTATE_RIGHT]
        target = _rng.uniform(
            settings.rotation_min_target_degrees,
            settings.rotation_max_target_degrees,
        )
        parameters = _comfortable_parameters(target, 15.0, 70.0)

    if previous_type in candidates and len(candidates) > 1:
        candidates = [item for item in candidates if item != previous_type]
    challenge_type = _rng.choice(candidates)
    return ChallengeDefinition(
        challenge_type=challenge_type,
        parameters=parameters,
        instruction=instruction_for(challenge_type),
        nonce=secrets.token_urlsafe(24),
    )
