from dataclasses import dataclass

from app.models.trust import VerificationSignalStatus, VerificationVerdict
from app.services.verification.domain import VerificationSignal, clamp01
from app.services.verification.policy import ResolvedPolicy


@dataclass(frozen=True)
class SignalContribution:
    signal: VerificationSignal
    configured_weight: float
    effective_weight: float
    contribution: float


@dataclass(frozen=True)
class ScoreCalculation:
    raw_score: float
    final_score: float
    overall_confidence: float
    contributions: list[SignalContribution]


def calculate_score(
    signals: list[VerificationSignal],
    policy: ResolvedPolicy,
) -> ScoreCalculation:
    available = [signal for signal in signals if signal.available]
    available_weight = sum(policy.weights.get(signal.type.value, 0.0) for signal in available)
    if available_weight <= 0:
        return ScoreCalculation(
            raw_score=0.0,
            final_score=0.0,
            overall_confidence=0.0,
            contributions=[
                SignalContribution(
                    signal=signal,
                    configured_weight=policy.weights.get(signal.type.value, 0.0),
                    effective_weight=0.0,
                    contribution=0.0,
                )
                for signal in signals
            ],
        )

    contributions: list[SignalContribution] = []
    score_points = 0.0
    confidence_points = 0.0
    for signal in signals:
        configured = float(policy.weights.get(signal.type.value, 0.0))
        if signal.available:
            effective = configured * 100.0 / available_weight
            contribution = signal.score * effective
            score_points += contribution
            confidence_points += signal.confidence * effective
        else:
            effective = 0.0
            contribution = 0.0
        contributions.append(
            SignalContribution(
                signal=signal,
                configured_weight=configured,
                effective_weight=effective,
                contribution=contribution,
            )
        )
    score = max(0.0, min(100.0, score_points))
    confidence = clamp01(confidence_points / 100.0)
    # Phase 7 keeps the numerical score transparent. Hard rules constrain the verdict rather
    # than secretly changing a number that was produced by the weighted evidence calculation.
    return ScoreCalculation(
        raw_score=score,
        final_score=score,
        overall_confidence=confidence,
        contributions=contributions,
    )


def required_evidence_is_insufficient(signals: list[VerificationSignal]) -> bool:
    return any(
        signal.required
        and (
            not signal.available
            or signal.status
            in {
                VerificationSignalStatus.INCONCLUSIVE,
                VerificationSignalStatus.UNAVAILABLE,
            }
        )
        for signal in signals
    )


def threshold_verdict(score: float, policy: ResolvedPolicy) -> VerificationVerdict:
    if score >= policy.verified_threshold:
        return VerificationVerdict.VERIFIED
    if score >= policy.review_threshold:
        return VerificationVerdict.REVIEW_REQUIRED
    return VerificationVerdict.FLAGGED
