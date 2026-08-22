from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trust import VerificationPolicy, VerificationSignalType
from app.services.verification.domain import PolicyDefinition

DEFAULT_POLICY_NAME = "Infrastructure Field Verification"
# v1.3 keeps the human-tolerant evidence weighting from v1.2 but raises automatic approval
# to a stricter 90/100 score. Captures below 90 remain reviewable instead of being auto-approved,
# while the 70% minimum confidence and all hard-rule anti-spoofing protections stay unchanged.
DEFAULT_POLICY_VERSION = "1.3"
DEFAULT_WEIGHTS = {
    VerificationSignalType.LOCATION: 20.0,
    VerificationSignalType.SESSION_TIME: 3.0,
    VerificationSignalType.CHALLENGE_COMPLETION: 45.0,
    VerificationSignalType.SENSOR_QUALITY: 1.0,
    VerificationSignalType.VISUAL_MOTION: 20.0,
    VerificationSignalType.SCENE_CONTINUITY: 10.0,
    VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY: 1.0,
}
# Only signals fundamental to a normal field proof are mandatory. Sensor quality, precise
# timing, scene continuity and visual-inertial fusion remain recorded/scored and can still
# constrain the verdict through hard rules. Inconclusive supporting measurements alone do not
# invalidate an otherwise strong genuine human capture.
DEFAULT_REQUIRED = frozenset(
    {
        VerificationSignalType.LOCATION,
        VerificationSignalType.CHALLENGE_COMPLETION,
        VerificationSignalType.VISUAL_MOTION,
    }
)
DEFAULT_HARD_RULES = frozenset(
    {
        "HIGH_CONFIDENCE_FUSION_MISMATCH",
        "CLEAR_WRONG_LOCATION",
        "MULTIPLE_HIGH_CONFIDENCE_CHALLENGE_FAILURES",
        "MAJOR_SCENE_DISCONTINUITY",
    }
)


def validate_policy(definition: PolicyDefinition) -> None:
    if not 0.0 <= definition.review_threshold <= 100.0:
        raise ValueError("Review threshold must be between 0 and 100")
    if not 0.0 <= definition.verified_threshold <= 100.0:
        raise ValueError("Verified threshold must be between 0 and 100")
    if definition.review_threshold >= definition.verified_threshold:
        raise ValueError("Review threshold must be lower than verified threshold")
    if not 0.0 <= definition.minimum_required_confidence <= 1.0:
        raise ValueError("Minimum confidence must be between 0 and 1")
    if set(definition.weights) != set(VerificationSignalType):
        raise ValueError("Policy weights must define every Phase 7 signal")
    if any(value < 0 for value in definition.weights.values()):
        raise ValueError("Policy weights cannot be negative")
    if abs(sum(definition.weights.values()) - 100.0) > 1e-6:
        raise ValueError("Policy weights must total 100")
    unknown_required = set(definition.required_signals) - set(VerificationSignalType)
    if unknown_required:
        raise ValueError(f"Unknown required signals: {unknown_required}")


def default_policy_definition() -> PolicyDefinition:
    definition = PolicyDefinition(
        name=DEFAULT_POLICY_NAME,
        version=DEFAULT_POLICY_VERSION,
        verified_threshold=90.0,
        review_threshold=65.0,
        minimum_required_confidence=0.70,
        weights=dict(DEFAULT_WEIGHTS),
        required_signals=DEFAULT_REQUIRED,
        hard_rules=DEFAULT_HARD_RULES,
    )
    validate_policy(definition)
    return definition


def policy_from_row(row: VerificationPolicy) -> PolicyDefinition:
    definition = PolicyDefinition(
        name=row.name,
        version=row.version,
        verified_threshold=row.verified_threshold,
        review_threshold=row.review_threshold,
        minimum_required_confidence=row.minimum_required_confidence,
        weights={
            VerificationSignalType(key): float(value)
            for key, value in (row.weights_json or {}).items()
        },
        required_signals=frozenset(
            VerificationSignalType(value) for value in (row.required_signals_json or [])
        ),
        hard_rules=frozenset(row.hard_rules_json or []),
    )
    validate_policy(definition)
    return definition


def get_or_create_default_policy(db: Session, organization_id: uuid.UUID) -> VerificationPolicy:
    existing = db.scalar(
        select(VerificationPolicy).where(
            VerificationPolicy.organization_id == organization_id,
            VerificationPolicy.name == DEFAULT_POLICY_NAME,
            VerificationPolicy.version == DEFAULT_POLICY_VERSION,
        )
    )
    if existing is not None:
        policy_from_row(existing)
        return existing

    definition = default_policy_definition()
    row = VerificationPolicy(
        organization_id=organization_id,
        name=definition.name,
        version=definition.version,
        active=True,
        verified_threshold=definition.verified_threshold,
        review_threshold=definition.review_threshold,
        minimum_required_confidence=definition.minimum_required_confidence,
        weights_json={key.value: value for key, value in definition.weights.items()},
        required_signals_json=[
            item.value for item in sorted(definition.required_signals, key=lambda item: item.value)
        ],
        hard_rules_json=sorted(definition.hard_rules),
    )
    db.add(row)
    db.flush()
    return row
