from __future__ import annotations

from app.models.trust import (
    VerificationSignalStatus,
    VerificationSignalType,
    VerificationVerdict,
)
from app.services.verification.domain import (
    EngineDecision,
    HardRuleResult,
    PolicyDefinition,
    ScoreBreakdown,
    VerificationSignal,
)


def calculate_score(
    signals: list[VerificationSignal],
    policy: PolicyDefinition,
) -> ScoreBreakdown:
    by_type = {item.type: item for item in signals}
    available = [
        signal_type
        for signal_type, signal in by_type.items()
        if signal.available and signal.status != VerificationSignalStatus.UNAVAILABLE
    ]
    available_weight = sum(policy.weights[item] for item in available)
    if available_weight <= 0:
        return ScoreBreakdown(0.0, 0.0, {}, 0.0)

    scale = 100.0 / available_weight
    contributions = {
        signal_type: by_type[signal_type].score * policy.weights[signal_type] * scale
        for signal_type in available
    }
    raw_score = max(0.0, min(100.0, sum(contributions.values())))
    confidence_numerator = sum(
        by_type[signal_type].confidence * policy.weights[signal_type]
        for signal_type in available
    )
    overall_confidence = confidence_numerator / available_weight
    return ScoreBreakdown(
        raw_score=round(raw_score, 4),
        overall_confidence=max(0.0, min(1.0, overall_confidence)),
        contributions=contributions,
        available_weight=available_weight,
    )


def _strong_fusion_mismatch(signal: VerificationSignal) -> bool:
    return (
        signal.type == VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY
        and signal.status == VerificationSignalStatus.FAIL
        and signal.confidence >= 0.80
        and signal.metrics.get("consistencyStatus") == "MISMATCH"
    )


def _clear_wrong_location(signal: VerificationSignal) -> bool:
    return (
        signal.type == VerificationSignalType.LOCATION
        and signal.status == VerificationSignalStatus.FAIL
        and signal.confidence >= 0.80
        and bool(signal.metrics.get("clearlyOutside"))
    )


def _multiple_challenge_failures(signal: VerificationSignal) -> bool:
    return (
        signal.type == VerificationSignalType.CHALLENGE_COMPLETION
        and int(signal.metrics.get("highConfidenceFailures") or 0) >= 2
    )


def _major_scene_discontinuity(signal: VerificationSignal) -> bool:
    return (
        signal.type == VerificationSignalType.SCENE_CONTINUITY
        and signal.status == VerificationSignalStatus.FAIL
        and signal.confidence >= 0.80
        and bool(signal.metrics.get("majorDiscontinuity"))
    )


def evaluate_hard_rules(
    signals: list[VerificationSignal],
    policy: PolicyDefinition,
) -> list[HardRuleResult]:
    rules: list[HardRuleResult] = []
    for signal in signals:
        if (
            "HIGH_CONFIDENCE_FUSION_MISMATCH" in policy.hard_rules
            and _strong_fusion_mismatch(signal)
        ):
            rules.append(
                HardRuleResult(
                    code="HIGH_CONFIDENCE_FUSION_MISMATCH",
                    maximum_verdict=VerificationVerdict.FLAGGED,
                    explanation=(
                        "High-confidence camera motion contradicted physical device motion."
                    ),
                )
            )
        if "CLEAR_WRONG_LOCATION" in policy.hard_rules and _clear_wrong_location(signal):
            rules.append(
                HardRuleResult(
                    code="CLEAR_WRONG_LOCATION",
                    maximum_verdict=VerificationVerdict.FLAGGED,
                    explanation=(
                        "High-confidence location evidence placed capture outside the allowed radius."
                    ),
                )
            )
        if (
            "MULTIPLE_HIGH_CONFIDENCE_CHALLENGE_FAILURES" in policy.hard_rules
            and _multiple_challenge_failures(signal)
        ):
            rules.append(
                HardRuleResult(
                    code="MULTIPLE_HIGH_CONFIDENCE_CHALLENGE_FAILURES",
                    maximum_verdict=VerificationVerdict.FLAGGED,
                    explanation="Multiple randomized challenges failed with strong sensor evidence.",
                )
            )
        if (
            "MAJOR_SCENE_DISCONTINUITY" in policy.hard_rules
            and _major_scene_discontinuity(signal)
        ):
            rules.append(
                HardRuleResult(
                    code="MAJOR_SCENE_DISCONTINUITY",
                    maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                    explanation="A major scene-continuity anomaly requires human review.",
                )
            )
    return list({item.code: item for item in rules}.values())


def _missing_required(
    signals: list[VerificationSignal],
    policy: PolicyDefinition,
) -> list[VerificationSignalType]:
    by_type = {item.type: item for item in signals}
    return [
        signal_type
        for signal_type in sorted(policy.required_signals, key=lambda item: item.value)
        if signal_type not in by_type
        or not by_type[signal_type].available
        or by_type[signal_type].status
        in {
            VerificationSignalStatus.UNAVAILABLE,
            VerificationSignalStatus.INCONCLUSIVE,
        }
    ]


def _base_verdict(score: float, policy: PolicyDefinition) -> VerificationVerdict:
    if score >= policy.verified_threshold:
        return VerificationVerdict.VERIFIED
    if score >= policy.review_threshold:
        return VerificationVerdict.REVIEW_REQUIRED
    return VerificationVerdict.FLAGGED


def resolve_decision(
    signals: list[VerificationSignal],
    policy: PolicyDefinition,
) -> EngineDecision:
    score = calculate_score(signals, policy)
    missing_required = _missing_required(signals, policy)
    hard_rules = evaluate_hard_rules(signals, policy)

    if missing_required:
        verdict = VerificationVerdict.INCONCLUSIVE
    else:
        verdict = _base_verdict(score.raw_score, policy)
        if (
            verdict == VerificationVerdict.VERIFIED
            and score.overall_confidence < policy.minimum_required_confidence
        ):
            verdict = VerificationVerdict.REVIEW_REQUIRED

        if any(item.maximum_verdict == VerificationVerdict.FLAGGED for item in hard_rules):
            verdict = VerificationVerdict.FLAGGED
        elif hard_rules and verdict == VerificationVerdict.VERIFIED:
            verdict = VerificationVerdict.REVIEW_REQUIRED

    serious = [item.explanation for item in hard_rules]
    positives = [
        reason
        for signal in signals
        if signal.status == VerificationSignalStatus.PASS
        for reason in signal.reasons[:1]
    ]
    summary_reasons = serious + positives
    if missing_required:
        summary_reasons.insert(
            0,
            "Required evidence was unavailable or inconclusive: "
            + ", ".join(item.value for item in missing_required)
            + ".",
        )

    warnings = [
        reason
        for signal in signals
        if signal.status
        in {VerificationSignalStatus.PARTIAL, VerificationSignalStatus.INCONCLUSIVE}
        for reason in signal.reasons[:1]
    ]
    if score.overall_confidence < policy.minimum_required_confidence:
        warnings.append(
            f"Overall evidence confidence {score.overall_confidence:.0%} is below the "
            f"{policy.minimum_required_confidence:.0%} automatic-verification threshold."
        )

    return EngineDecision(
        score=score.raw_score,
        confidence=score.overall_confidence,
        verdict=verdict,
        hard_rules=hard_rules,
        summary_reasons=summary_reasons[:8],
        warnings=warnings[:8],
    )
