from app.models.trust import VerificationSignalStatus, VerificationSignalType, VerificationVerdict
from app.services.verification.domain import HardRuleFinding, VerificationSignal


_LABELS = {
    VerificationSignalType.LOCATION: "Location",
    VerificationSignalType.SESSION_TIME: "Session timing",
    VerificationSignalType.CHALLENGE_COMPLETION: "Random challenges",
    VerificationSignalType.SENSOR_EVIDENCE: "Sensor evidence",
    VerificationSignalType.VISUAL_EVIDENCE: "Visual evidence",
    VerificationSignalType.SCENE_CONTINUITY: "Scene continuity",
    VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY: "Camera–sensor consistency",
}


def _signal_sentence(signal: VerificationSignal) -> str:
    prefix = _LABELS[signal.type]
    if signal.reasons:
        return signal.reasons[0]
    return f"{prefix} returned {signal.status.value}."


def build_explanation(
    *,
    verdict: VerificationVerdict,
    signals: list[VerificationSignal],
    hard_rules: list[HardRuleFinding],
    overall_confidence: float,
) -> tuple[str, list[str], list[str]]:
    reasons: list[str] = []
    warnings: list[str] = []

    # Serious policy findings come first.
    for finding in hard_rules:
        warnings.append(finding.message)

    # Mandatory failures/ambiguity come before positive supporting evidence.
    for signal in signals:
        if not signal.required:
            continue
        if not signal.available or signal.status in {
            VerificationSignalStatus.FAIL,
            VerificationSignalStatus.INCONCLUSIVE,
            VerificationSignalStatus.UNAVAILABLE,
        }:
            warnings.append(_signal_sentence(signal))

    for signal in signals:
        if signal.status == VerificationSignalStatus.PARTIAL:
            warnings.append(_signal_sentence(signal))

    for signal in signals:
        if signal.available and signal.status == VerificationSignalStatus.PASS:
            reasons.append(_signal_sentence(signal))

    if overall_confidence < 0.70:
        warnings.append(
            f"Overall evidence confidence is {overall_confidence * 100:.0f}%, below the default automatic-verification confidence target."
        )

    warnings.append(
        "The SiteProof score is multi-signal confidence under the configured policy, not legal certainty or proof against every sophisticated attack."
    )

    summary = {
        VerificationVerdict.VERIFIED: "Evidence strongly satisfies the configured SiteProof verification policy.",
        VerificationVerdict.REVIEW_REQUIRED: "Evidence is mostly usable but one or more signals require human review.",
        VerificationVerdict.FLAGGED: "Strong contradictory or failing evidence was detected under the configured policy.",
        VerificationVerdict.INCONCLUSIVE: "Required evidence is missing or technically insufficient for a reliable automated decision.",
    }[verdict]
    return summary, _dedupe(reasons), _dedupe(warnings)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
