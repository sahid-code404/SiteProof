from app.models.trust import VerificationSignalStatus, VerificationSignalType
from app.services.verification.domain import HardRuleFinding, VerificationSignal
from app.services.verification.policy import ResolvedPolicy


def _by_type(signals: list[VerificationSignal]) -> dict[VerificationSignalType, VerificationSignal]:
    return {signal.type: signal for signal in signals}


def evaluate_hard_rules(
    signals: list[VerificationSignal],
    policy: ResolvedPolicy,
) -> list[HardRuleFinding]:
    findings: list[HardRuleFinding] = []
    signal_map = _by_type(signals)

    fusion_rule = policy.hard_rules.get("highConfidenceFusionMismatch") or {}
    fusion = signal_map.get(VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY)
    if fusion_rule.get("enabled") and fusion and fusion.status == VerificationSignalStatus.FAIL:
        threshold = float(fusion_rule.get("minimumConfidence", 0.80))
        mismatches = list(fusion.metrics.get("mismatches") or [])
        if any(float(item.get("confidence") or 0.0) >= threshold for item in mismatches):
            findings.append(
                HardRuleFinding(
                    code="HIGH_CONFIDENCE_FUSION_MISMATCH",
                    severity=str(fusion_rule.get("verdict", "FLAGGED")),
                    message="A high-confidence camera–sensor consistency mismatch blocks automatic verification.",
                )
            )

    location_rule = policy.hard_rules.get("highConfidenceWrongLocation") or {}
    location = signal_map.get(VerificationSignalType.LOCATION)
    if (
        location_rule.get("enabled")
        and location
        and location.status == VerificationSignalStatus.FAIL
        and location.confidence >= float(location_rule.get("minimumConfidence", 0.80))
    ):
        findings.append(
            HardRuleFinding(
                code="HIGH_CONFIDENCE_WRONG_LOCATION",
                severity=str(location_rule.get("verdict", "FLAGGED")),
                message="High-confidence location evidence places the capture outside the permitted site radius.",
            )
        )

    challenge_rule = policy.hard_rules.get("multipleHighConfidenceChallengeFailures") or {}
    challenges = signal_map.get(VerificationSignalType.CHALLENGE_COMPLETION)
    if challenge_rule.get("enabled") and challenges:
        minimum = int(challenge_rule.get("minimumFailures", 2))
        count = int(challenges.metrics.get("highConfidenceFailures") or 0)
        if count >= minimum:
            findings.append(
                HardRuleFinding(
                    code="MULTIPLE_HIGH_CONFIDENCE_CHALLENGE_FAILURES",
                    severity=str(challenge_rule.get("verdict", "FLAGGED")),
                    message=f"{count} randomized challenges failed with high-confidence sensor evidence.",
                )
            )

    continuity_rule = policy.hard_rules.get("majorSceneDiscontinuity") or {}
    continuity = signal_map.get(VerificationSignalType.SCENE_CONTINUITY)
    if continuity_rule.get("enabled") and continuity and continuity.available:
        threshold = float(continuity_rule.get("maximumContinuityScore", 0.40))
        minimum_confidence = float(continuity_rule.get("minimumConfidence", 0.80))
        minimum_observed = continuity.metrics.get("minimumContinuityScore")
        if (
            isinstance(minimum_observed, (int, float))
            and float(minimum_observed) <= threshold
            and continuity.confidence >= minimum_confidence
        ):
            findings.append(
                HardRuleFinding(
                    code="MAJOR_SCENE_DISCONTINUITY",
                    severity=str(continuity_rule.get("verdict", "REVIEW_REQUIRED")),
                    message="A high-confidence scene-continuity anomaly requires human review.",
                )
            )
    return findings
