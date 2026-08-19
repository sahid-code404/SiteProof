from statistics import fmean

from app.core.config import get_settings
from app.models.challenge import ChallengeResult, ChallengeStatus, VerificationChallenge
from app.models.trust import VerificationSignalStatus, VerificationSignalType
from app.models.verification import VerificationSession
from app.services.verification.domain import VerificationSignal, clamp01
from app.services.verification.policy import ResolvedPolicy


def _required(policy: ResolvedPolicy, kind: VerificationSignalType) -> bool:
    return kind.value in policy.required_signals


def challenge_signal(
    challenges: list[VerificationChallenge],
    policy: ResolvedPolicy,
) -> VerificationSignal:
    kind = VerificationSignalType.CHALLENGE_COMPLETION
    expected = get_settings().challenge_count
    if not challenges:
        return VerificationSignal(
            kind,
            VerificationSignalStatus.UNAVAILABLE,
            0,
            0,
            False,
            _required(policy, kind),
            ["No randomized challenge results are available."],
        )

    values: list[float] = []
    confidences: list[float] = []
    passed = 0
    inconclusive = 0
    failed = 0
    expired = 0
    retries = 0
    high_conf_failures = 0

    for challenge in challenges:
        retries += max(0, challenge.attempt_number - 1)
        confidence = clamp01(float(challenge.sensor_score or 0.0))
        validation = clamp01(float(challenge.validation_score or 0.0))
        confidences.append(confidence)
        if challenge.result == ChallengeResult.PASS:
            passed += 1
            values.append(max(0.75, validation))
        elif challenge.result == ChallengeResult.INCONCLUSIVE:
            inconclusive += 1
            values.append(min(0.50, validation if validation > 0 else 0.35))
        elif challenge.result == ChallengeResult.FAIL:
            failed += 1
            values.append(0.0)
            high_conf_failures += int(confidence >= 0.80)
        elif challenge.status == ChallengeStatus.EXPIRED:
            expired += 1
            values.append(0.0)
        else:
            values.append(0.0)

    score = fmean(values) if values else 0.0
    if retries:
        score *= max(0.80, 1.0 - 0.05 * retries)

    metrics = {
        "required": expected,
        "observed": len(challenges),
        "passed": passed,
        "inconclusive": inconclusive,
        "failed": failed,
        "expired": expired,
        "retries": retries,
        "highConfidenceFailures": high_conf_failures,
    }
    if len(challenges) < expected:
        status = VerificationSignalStatus.INCONCLUSIVE
        reasons = [
            f"Only {len(challenges)} of {expected} required challenge results are available."
        ]
    elif failed or expired:
        status = VerificationSignalStatus.FAIL
        reasons = [f"{failed + expired} randomized challenge(s) failed or expired."]
    elif inconclusive:
        status = VerificationSignalStatus.PARTIAL
        reasons = [f"{passed} challenge(s) passed and {inconclusive} were inconclusive."]
    else:
        status = VerificationSignalStatus.PASS
        reasons = [f"All {passed} randomized challenges passed."]

    return VerificationSignal(
        kind,
        status,
        score,
        fmean(confidences) if confidences else 0,
        True,
        _required(policy, kind),
        reasons,
        metrics,
        "challenge-v1.0",
    )


def sensor_signal(
    challenges: list[VerificationChallenge],
    session: VerificationSession,
    policy: ResolvedPolicy,
) -> VerificationSignal:
    kind = VerificationSignalType.SENSOR_EVIDENCE
    capabilities = session.device_capabilities or {}
    if not capabilities.get("gyroscope"):
        return VerificationSignal(
            kind,
            VerificationSignalStatus.UNAVAILABLE,
            0,
            0,
            False,
            _required(policy, kind),
            ["Gyroscope capability required by the current challenge set is unavailable."],
        )

    scores = [
        float(item.sensor_score)
        for item in challenges
        if item.sensor_score is not None
    ]
    if not scores:
        return VerificationSignal(
            kind,
            VerificationSignalStatus.UNAVAILABLE,
            0,
            0,
            False,
            _required(policy, kind),
            ["No Phase 4 sensor-quality scores are available."],
        )

    score = clamp01(fmean(scores))
    good = 0
    gaps: list[float] = []
    for challenge in challenges:
        gyro = (challenge.sensor_quality_json or {}).get("gyroscope") or {}
        good += int(gyro.get("quality") == "GOOD")
        gap = gyro.get("maxGapMs")
        if isinstance(gap, (int, float)):
            gaps.append(float(gap))

    ratio = good / max(len(challenges), 1)
    confidence = clamp01(0.65 * score + 0.35 * ratio)
    if score >= 0.80 and ratio >= 0.67:
        status = VerificationSignalStatus.PASS
        reasons = ["Gyroscope/rotation-vector evidence quality and agreement were strong."]
    elif score >= 0.55:
        status = VerificationSignalStatus.PARTIAL
        reasons = [
            "Sensor evidence was usable but some quality/agreement metrics were degraded."
        ]
    else:
        status = VerificationSignalStatus.INCONCLUSIVE
        reasons = ["Sensor evidence quality is too low for a reliable verification contribution."]

    metrics = {
        "gyroscopeAvailable": True,
        "rotationVectorAvailable": bool(capabilities.get("rotation_vector")),
        "goodQualityChallenges": good,
        "challengeCount": len(challenges),
        "maxObservedGapMs": max(gaps) if gaps else None,
    }
    return VerificationSignal(
        kind,
        status,
        score,
        confidence,
        True,
        _required(policy, kind),
        reasons,
        metrics,
        "phase4-sensor-v1.0",
    )
