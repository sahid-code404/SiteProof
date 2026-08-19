from statistics import fmean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.challenge import VerificationChallenge
from app.models.fusion import ConsistencyStatus, FusionAnalysisStatus, VisualInertialResult
from app.models.trust import VerificationSignalStatus, VerificationSignalType
from app.models.visual_motion import VisualAnalysisStatus, VisualMotionResult, VisualQuality
from app.services.verification.domain import VerificationSignal, clamp01
from app.services.verification.policy import ResolvedPolicy


def _required(policy: ResolvedPolicy, kind: VerificationSignalType) -> bool:
    return kind.value in policy.required_signals


def visual_rows(
    db: Session,
    challenges: list[VerificationChallenge],
) -> list[VisualMotionResult]:
    if not challenges:
        return []
    challenge_ids = [item.id for item in challenges]
    return list(
        db.scalars(
            select(VisualMotionResult).where(
                VisualMotionResult.challenge_id.in_(challenge_ids),
                VisualMotionResult.analysis_version == get_settings().vision_analysis_version,
            )
        ).all()
    )


def fusion_rows(
    db: Session,
    challenges: list[VerificationChallenge],
) -> list[VisualInertialResult]:
    if not challenges:
        return []
    challenge_ids = [item.id for item in challenges]
    return list(
        db.scalars(
            select(VisualInertialResult).where(
                VisualInertialResult.challenge_id.in_(challenge_ids),
                VisualInertialResult.fusion_version == get_settings().fusion_analysis_version,
            )
        ).all()
    )


def visual_signal(
    rows: list[VisualMotionResult],
    challenges: list[VerificationChallenge],
    policy: ResolvedPolicy,
) -> VerificationSignal:
    kind = VerificationSignalType.VISUAL_EVIDENCE
    if not rows:
        return VerificationSignal(
            kind,
            VerificationSignalStatus.UNAVAILABLE,
            0,
            0,
            False,
            _required(policy, kind),
            ["No Phase 5 visual-motion results are available."],
        )

    by_id = {row.challenge_id: row for row in rows}
    if any(
        by_id.get(challenge.id) is None
        or by_id[challenge.id].analysis_status
        in {VisualAnalysisStatus.PENDING, VisualAnalysisStatus.PROCESSING}
        for challenge in challenges
    ):
        return VerificationSignal(
            kind,
            VerificationSignalStatus.UNAVAILABLE,
            0,
            0,
            False,
            _required(policy, kind),
            ["Visual analysis is still processing."],
            {"processing": True},
            get_settings().vision_analysis_version,
        )

    scores: list[float] = []
    confidences: list[float] = []
    successful = 0
    partial = 0
    failed = 0
    for challenge in challenges:
        row = by_id[challenge.id]
        confidences.append(clamp01(row.visual_confidence))
        if row.analysis_status == VisualAnalysisStatus.SUCCESS:
            successful += 1
            quality = {
                VisualQuality.GOOD: 1.0,
                VisualQuality.FAIR: 0.75,
                VisualQuality.POOR: 0.45,
            }[row.visual_quality]
            scores.append(
                0.50 * quality
                + 0.30 * clamp01(row.inlier_ratio)
                + 0.20 * (1.0 - clamp01(row.invalid_frame_ratio))
            )
        elif row.analysis_status == VisualAnalysisStatus.INCONCLUSIVE:
            partial += 1
            scores.append(0.35)
        else:
            failed += 1
            scores.append(0.0)

    score = clamp01(fmean(scores))
    confidence = clamp01(fmean(confidences))
    if failed and successful == 0:
        status = VerificationSignalStatus.INCONCLUSIVE
        reasons = ["Visual analysis failed for the required challenge evidence."]
    elif partial or failed:
        status = VerificationSignalStatus.PARTIAL
        reasons = [
            f"Visual evidence was reliable for {successful} of {len(challenges)} challenge(s)."
        ]
    elif score >= 0.80:
        status = VerificationSignalStatus.PASS
        reasons = ["Phase 5 produced well-supported visual motion across the challenge sequence."]
    else:
        status = VerificationSignalStatus.PARTIAL
        reasons = ["Visual motion was available but quality/support was only moderate."]

    return VerificationSignal(
        kind,
        status,
        score,
        confidence,
        True,
        _required(policy, kind),
        reasons,
        {
            "successfulChallenges": successful,
            "partialChallenges": partial,
            "failedChallenges": failed,
        },
        get_settings().vision_analysis_version,
    )


def continuity_signal(
    rows: list[VisualMotionResult],
    challenges: list[VerificationChallenge],
    policy: ResolvedPolicy,
) -> VerificationSignal:
    kind = VerificationSignalType.SCENE_CONTINUITY
    terminal = [
        row
        for row in rows
        if row.analysis_status
        in {VisualAnalysisStatus.SUCCESS, VisualAnalysisStatus.INCONCLUSIVE}
    ]
    if len(terminal) != len(challenges) or not terminal:
        return VerificationSignal(
            kind,
            VerificationSignalStatus.UNAVAILABLE,
            0,
            0,
            False,
            _required(policy, kind),
            ["Scene-continuity metrics are incomplete."],
            source_algorithm_version=get_settings().vision_analysis_version,
        )

    scores = [clamp01(row.scene_continuity_score) for row in terminal]
    confidence = clamp01(fmean(row.visual_confidence for row in terminal))
    duplicate = max((row.duplicate_frame_ratio for row in terminal), default=0.0)
    freeze = max((row.freeze_duration_ms for row in terminal), default=0)
    invalid = max((row.invalid_frame_ratio for row in terminal), default=0.0)
    score = clamp01(
        fmean(scores)
        * (1.0 - 0.25 * clamp01(duplicate))
        * (1.0 - 0.25 * clamp01(invalid))
    )
    if min(scores) < 0.40:
        status = VerificationSignalStatus.FAIL
        reasons = ["A major scene-continuity anomaly was detected during at least one challenge."]
    elif score < 0.75:
        status = VerificationSignalStatus.PARTIAL
        reasons = [
            "Video continuity was usable but contained continuity/freeze/invalid-frame warnings."
        ]
    else:
        status = VerificationSignalStatus.PASS
        reasons = ["No major scene-continuity anomaly was found in the challenge windows."]

    metrics = {
        "minimumContinuityScore": round(min(scores), 4),
        "maximumDuplicateFrameRatio": round(float(duplicate), 4),
        "maximumFreezeDurationMs": int(freeze),
        "maximumInvalidFrameRatio": round(float(invalid), 4),
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
        get_settings().vision_analysis_version,
    )


def fusion_signal(
    rows: list[VisualInertialResult],
    challenges: list[VerificationChallenge],
    policy: ResolvedPolicy,
) -> VerificationSignal:
    kind = VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY
    if not rows:
        return VerificationSignal(
            kind,
            VerificationSignalStatus.UNAVAILABLE,
            0,
            0,
            False,
            _required(policy, kind),
            ["No Phase 6 visual-inertial results are available."],
        )

    by_id = {row.challenge_id: row for row in rows}
    if any(
        by_id.get(challenge.id) is None
        or by_id[challenge.id].analysis_status
        in {FusionAnalysisStatus.PENDING, FusionAnalysisStatus.PROCESSING}
        for challenge in challenges
    ):
        return VerificationSignal(
            kind,
            VerificationSignalStatus.UNAVAILABLE,
            0,
            0,
            False,
            _required(policy, kind),
            ["Visual-inertial fusion is still processing."],
            {"processing": True},
            get_settings().fusion_analysis_version,
        )

    scores: list[float] = []
    confidences: list[float] = []
    mismatches = 0
    partial = 0
    inconclusive = 0
    failed = 0
    details: list[dict] = []
    for challenge in challenges:
        row = by_id[challenge.id]
        confidence = clamp01(float(row.fusion_confidence or 0))
        confidences.append(confidence)
        if row.analysis_status == FusionAnalysisStatus.FAILED:
            failed += 1
            scores.append(0)
            continue

        scores.append(clamp01(float(row.effective_consistency_score or 0)))
        if row.consistency_status == ConsistencyStatus.MISMATCH:
            mismatches += 1
            details.append(
                {
                    "challengeId": str(challenge.id),
                    "sequenceNumber": challenge.sequence_number,
                    "confidence": confidence,
                    "reasons": list(row.mismatch_reasons_json or []),
                }
            )
        elif row.consistency_status == ConsistencyStatus.PARTIALLY_CONSISTENT:
            partial += 1
        elif row.consistency_status == ConsistencyStatus.INCONCLUSIVE:
            inconclusive += 1

    score = clamp01(fmean(scores))
    confidence = clamp01(fmean(confidences))
    if failed == len(challenges):
        status = VerificationSignalStatus.INCONCLUSIVE
        reasons = ["Fusion analysis failed technically for all required challenge evidence."]
    elif mismatches:
        status = VerificationSignalStatus.FAIL
        reasons = [
            f"{mismatches} challenge(s) contained a camera–sensor consistency mismatch."
        ]
    elif inconclusive == len(challenges):
        status = VerificationSignalStatus.INCONCLUSIVE
        reasons = ["Camera–sensor consistency was inconclusive for all required challenges."]
    elif partial or inconclusive or failed:
        status = VerificationSignalStatus.PARTIAL
        reasons = ["Camera–sensor consistency was mixed or incomplete across the challenge sequence."]
    else:
        status = VerificationSignalStatus.PASS
        reasons = [
            "Camera motion and physical device motion were mutually consistent across the challenge sequence."
        ]

    metrics = {
        "mismatchChallenges": mismatches,
        "partialChallenges": partial,
        "inconclusiveChallenges": inconclusive,
        "failedChallenges": failed,
        "mismatches": details,
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
        get_settings().fusion_analysis_version,
    )
