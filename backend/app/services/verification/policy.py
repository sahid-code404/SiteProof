from dataclasses import dataclass
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trust import VerificationPolicy, VerificationSignalType

DEFAULT_POLICY_NAME = "Infrastructure Field Verification"
DEFAULT_POLICY_VERSION = "1.0"
ENGINE_VERSION = "verification-engine-v1.0"

DEFAULT_WEIGHTS = {
    VerificationSignalType.LOCATION.value: 15.0,
    VerificationSignalType.SESSION_TIME.value: 5.0,
    VerificationSignalType.CHALLENGE_COMPLETION.value: 20.0,
    VerificationSignalType.SENSOR_EVIDENCE.value: 15.0,
    VerificationSignalType.VISUAL_EVIDENCE.value: 10.0,
    VerificationSignalType.SCENE_CONTINUITY.value: 10.0,
    VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY.value: 25.0,
}

DEFAULT_REQUIRED_SIGNALS = [
    VerificationSignalType.LOCATION.value,
    VerificationSignalType.SESSION_TIME.value,
    VerificationSignalType.CHALLENGE_COMPLETION.value,
    VerificationSignalType.SENSOR_EVIDENCE.value,
    VerificationSignalType.VISUAL_EVIDENCE.value,
    VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY.value,
]

DEFAULT_HARD_RULES = {
    "highConfidenceFusionMismatch": {
        "enabled": True,
        "minimumConfidence": 0.80,
        "verdict": "FLAGGED",
    },
    "highConfidenceWrongLocation": {
        "enabled": True,
        "minimumConfidence": 0.80,
        "verdict": "FLAGGED",
    },
    "multipleHighConfidenceChallengeFailures": {
        "enabled": True,
        "minimumConfidence": 0.80,
        "minimumFailures": 2,
        "verdict": "FLAGGED",
    },
    "majorSceneDiscontinuity": {
        "enabled": True,
        "minimumConfidence": 0.80,
        "maximumContinuityScore": 0.40,
        "verdict": "REVIEW_REQUIRED",
    },
}


@dataclass(frozen=True)
class ResolvedPolicy:
    id: uuid.UUID
    name: str
    version: str
    verified_threshold: float
    review_threshold: float
    minimum_required_confidence: float
    weights: dict[str, float]
    required_signals: frozenset[str]
    hard_rules: dict[str, Any]


def validate_policy_values(
    *,
    verified_threshold: float,
    review_threshold: float,
    minimum_required_confidence: float,
    weights: dict[str, float],
    required_signals: list[str],
    hard_rules: dict[str, Any],
) -> None:
    valid_types = {item.value for item in VerificationSignalType}
    if not 0 <= review_threshold < verified_threshold <= 100:
        raise ValueError("Verification thresholds must satisfy 0 <= review < verified <= 100.")
    if not 0 <= minimum_required_confidence <= 1:
        raise ValueError("Minimum required confidence must be between 0 and 1.")
    if set(weights) != valid_types:
        raise ValueError("Policy weights must define every current verification signal exactly once.")
    if any(not isinstance(value, (int, float)) or value < 0 for value in weights.values()):
        raise ValueError("Policy weights must be non-negative numeric values.")
    total = sum(float(value) for value in weights.values())
    if abs(total - 100.0) > 0.001:
        raise ValueError("Policy weights must total 100.")
    if not required_signals or any(item not in valid_types for item in required_signals):
        raise ValueError("Required signals contain an unsupported verification signal.")
    if len(set(required_signals)) != len(required_signals):
        raise ValueError("Required signals must not contain duplicates.")
    required_rule_names = {
        "highConfidenceFusionMismatch",
        "highConfidenceWrongLocation",
        "multipleHighConfidenceChallengeFailures",
        "majorSceneDiscontinuity",
    }
    if not required_rule_names.issubset(set(hard_rules)):
        raise ValueError("Policy hard-rule configuration is incomplete.")
    valid_rule_verdicts = {"FLAGGED", "REVIEW_REQUIRED"}
    for name in required_rule_names:
        rule = hard_rules.get(name)
        if not isinstance(rule, dict):
            raise ValueError(f"Hard rule {name} must be an object.")
        if not isinstance(rule.get("enabled"), bool):
            raise ValueError(f"Hard rule {name} must define a boolean enabled flag.")
        verdict = str(rule.get("verdict", ""))
        if verdict not in valid_rule_verdicts:
            raise ValueError(f"Hard rule {name} has an unsupported verdict constraint.")
        if "minimumConfidence" in rule:
            value = rule["minimumConfidence"]
            if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                raise ValueError(f"Hard rule {name} minimumConfidence must be between 0 and 1.")
    challenge_rule = hard_rules["multipleHighConfidenceChallengeFailures"]
    if int(challenge_rule.get("minimumFailures", 0)) < 1:
        raise ValueError("Challenge-failure hard rule must require at least one failure.")
    continuity_rule = hard_rules["majorSceneDiscontinuity"]
    continuity_threshold = continuity_rule.get("maximumContinuityScore")
    if not isinstance(continuity_threshold, (int, float)) or not 0 <= float(continuity_threshold) <= 1:
        raise ValueError("Scene-continuity hard-rule threshold must be between 0 and 1.")


def _resolved(row: VerificationPolicy) -> ResolvedPolicy:
    validate_policy_values(
        verified_threshold=row.verified_threshold,
        review_threshold=row.review_threshold,
        minimum_required_confidence=row.minimum_required_confidence,
        weights=dict(row.weights_json),
        required_signals=list(row.required_signals_json),
        hard_rules=dict(row.hard_rules_json),
    )
    return ResolvedPolicy(
        id=row.id,
        name=row.name,
        version=row.version,
        verified_threshold=row.verified_threshold,
        review_threshold=row.review_threshold,
        minimum_required_confidence=row.minimum_required_confidence,
        weights={key: float(value) for key, value in row.weights_json.items()},
        required_signals=frozenset(str(item) for item in row.required_signals_json),
        hard_rules=dict(row.hard_rules_json),
    )


def ensure_default_policy(db: Session) -> VerificationPolicy:
    row = db.scalar(
        select(VerificationPolicy).where(
            VerificationPolicy.organization_id.is_(None),
            VerificationPolicy.name == DEFAULT_POLICY_NAME,
            VerificationPolicy.version == DEFAULT_POLICY_VERSION,
        )
    )
    if row is not None:
        return row
    validate_policy_values(
        verified_threshold=85.0,
        review_threshold=65.0,
        minimum_required_confidence=0.70,
        weights=DEFAULT_WEIGHTS,
        required_signals=DEFAULT_REQUIRED_SIGNALS,
        hard_rules=DEFAULT_HARD_RULES,
    )
    row = VerificationPolicy(
        organization_id=None,
        name=DEFAULT_POLICY_NAME,
        version=DEFAULT_POLICY_VERSION,
        active=True,
        verified_threshold=85.0,
        review_threshold=65.0,
        minimum_required_confidence=0.70,
        weights_json=DEFAULT_WEIGHTS,
        required_signals_json=DEFAULT_REQUIRED_SIGNALS,
        hard_rules_json=DEFAULT_HARD_RULES,
    )
    db.add(row)
    db.flush()
    return row


def resolve_policy(
    db: Session,
    *,
    organization_id,
    version: str | None = None,
) -> ResolvedPolicy:
    ensure_default_policy(db)
    statement = select(VerificationPolicy).where(
        VerificationPolicy.organization_id == organization_id,
    )
    if version:
        statement = statement.where(VerificationPolicy.version == version)
    else:
        statement = statement.where(VerificationPolicy.active.is_(True))
    statement = statement.order_by(VerificationPolicy.updated_at.desc())
    row = db.scalar(statement)
    if row is None:
        statement = select(VerificationPolicy).where(
            VerificationPolicy.organization_id.is_(None),
        )
        if version:
            statement = statement.where(VerificationPolicy.version == version)
        else:
            statement = statement.where(VerificationPolicy.active.is_(True))
        row = db.scalar(statement.order_by(VerificationPolicy.updated_at.desc()))
    if row is None:
        raise ValueError("No active verification policy is available.")
    return _resolved(row)
