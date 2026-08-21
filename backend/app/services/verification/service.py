from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.models.fusion import FusionAnalysisStatus, VisualInertialResult
from app.models.inspection import Inspection
from app.models.trust import (
    VerificationProcessingStatus,
    VerificationResult,
    VerificationSignalResult,
    VerificationVerdict,
)
from app.models.user import User
from app.models.verification import VerificationSession
from app.models.visual_motion import VisualAnalysisStatus, VisualMotionResult
from app.services.audit_service import record_audit
from app.services.verification.collectors import SignalCollector
from app.services.verification.policy import get_or_create_default_policy, policy_from_row
from app.services.verification.scoring import calculate_score, resolve_decision
from app.services.verification.security_gate import (
    LEGACY_ENGINE_VERSION,
    SECURITY_ENGINE_VERSION,
    apply_security_gate,
    engine_version_for_session,
    evaluate_security_gate,
)

# Compatibility export for older callers/tests. calculate_verification selects the engine
# per session: v1.1 when Phase 9/10 analysis is unavailable, v2.0 once the security pipeline
# has completed. This keeps historical v1.1 decisions intact while new complete pipelines use v2.
ENGINE_VERSION = LEGACY_ENGINE_VERSION
LIMITATIONS = [
    "The SiteProof score is confidence derived from configured multi-signal policy, not legal certainty.",
    "The result depends on phone hardware, scene quality, upstream algorithms, and policy configuration.",
    "Sophisticated synchronized replay or compromised device/OS behavior may remain undetected.",
    "Human review remains appropriate for high-risk or ambiguous operational decisions.",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_current_result(
    db: Session,
    session_id: uuid.UUID,
    policy_id: uuid.UUID,
    policy_version: str,
    engine_version: str,
) -> VerificationResult | None:
    return db.scalar(
        select(VerificationResult).where(
            VerificationResult.session_id == session_id,
            VerificationResult.policy_id == policy_id,
            VerificationResult.policy_version == policy_version,
            VerificationResult.engine_version == engine_version,
        )
    )


def _upstream_processing(db: Session, session_id: uuid.UUID) -> list[str]:
    settings = get_settings()
    waiting: list[str] = []
    visual_rows = list(
        db.scalars(
            select(VisualMotionResult).where(
                VisualMotionResult.session_id == session_id,
                VisualMotionResult.analysis_version == settings.vision_analysis_version,
            )
        ).all()
    )
    if any(
        row.analysis_status in {VisualAnalysisStatus.PENDING, VisualAnalysisStatus.PROCESSING}
        for row in visual_rows
    ):
        waiting.append("VISUAL_MOTION")

    fusion_rows = list(
        db.scalars(
            select(VisualInertialResult).where(
                VisualInertialResult.session_id == session_id,
                VisualInertialResult.fusion_version == settings.fusion_analysis_version,
            )
        ).all()
    )
    if any(
        row.analysis_status in {FusionAnalysisStatus.PENDING, FusionAnalysisStatus.PROCESSING}
        for row in fusion_rows
    ):
        waiting.append("VISUAL_INERTIAL_CONSISTENCY")
    return waiting


def _reset_incomplete_result(db: Session, result: VerificationResult) -> None:
    """Reset only unfinished rows; completed automated decisions are immutable."""
    if result.processing_status == VerificationProcessingStatus.COMPLETED:
        raise RuntimeError("Completed verification results are immutable; bump engine version instead.")
    result.processing_status = VerificationProcessingStatus.CALCULATING
    result.raw_score = None
    result.final_score = None
    result.verdict = None
    result.overall_confidence = None
    result.hard_rule_triggered = False
    result.hard_rule_codes_json = []
    result.summary = None
    result.summary_reasons_json = []
    result.warnings_json = []
    result.limitations_json = []
    result.diagnostics_json = None
    result.calculated_at = None
    db.execute(
        delete(VerificationSignalResult).where(
            VerificationSignalResult.verification_result_id == result.id
        )
    )


def calculate_verification(
    db: Session,
    session_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID | None = None,
    force: bool = False,
) -> VerificationResult:
    session = db.get(VerificationSession, session_id)
    if session is None:
        raise ValueError("Verification session does not exist")
    inspection = db.get(Inspection, session.inspection_id)
    if inspection is None or inspection.organization_id != session.organization_id:
        raise ValueError("Inspection does not match verification session")

    policy_row = get_or_create_default_policy(db, session.organization_id)
    policy = policy_from_row(policy_row)
    engine_version = engine_version_for_session(db, session.id)
    existing = _latest_current_result(
        db,
        session.id,
        policy_row.id,
        policy.version,
        engine_version,
    )

    # Automated decisions and any receipts derived from them are historical records. `force`
    # may resume/retry an unfinished calculation, but it never rewrites a completed decision.
    if existing is not None and existing.processing_status == VerificationProcessingStatus.COMPLETED:
        return existing

    result = existing or VerificationResult(
        organization_id=session.organization_id,
        inspection_id=session.inspection_id,
        session_id=session.id,
        policy_id=policy_row.id,
        policy_name=policy.name,
        policy_version=policy.version,
        engine_version=engine_version,
        processing_status=VerificationProcessingStatus.CALCULATING,
    )
    if existing is None:
        db.add(result)
        db.flush()
    else:
        _reset_incomplete_result(db, result)

    actor = actor_user_id or session.created_by_user_id
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=actor,
        entity_type="VERIFICATION_RESULT",
        entity_id=result.id,
        action="VERIFICATION_STARTED",
        metadata={
            "engineVersion": engine_version,
            "policyVersion": policy.version,
            "forced": force,
        },
    )

    upstream_processing = _upstream_processing(db, session.id)
    if upstream_processing:
        result.processing_status = VerificationProcessingStatus.WAITING_FOR_SIGNALS
        result.summary = "Waiting for required upstream verification analysis to finish."
        result.diagnostics_json = {"waitingFor": upstream_processing}
        db.commit()
        return result

    signals = SignalCollector(db, session, inspection).collect(policy.required_signals)
    required_not_ready = [signal for signal in signals if signal.required and not signal.available]
    if required_not_ready:
        result.processing_status = VerificationProcessingStatus.WAITING_FOR_SIGNALS
        result.summary = "Waiting for required upstream verification signals."
        result.diagnostics_json = {
            "waitingFor": [signal.type.value for signal in required_not_ready],
        }
        db.commit()
        return result

    score = calculate_score(signals, policy)
    decision = resolve_decision(signals, policy)
    security_rules = []
    if engine_version == SECURITY_ENGINE_VERSION:
        security_rules = evaluate_security_gate(db, session.id)
        decision = apply_security_gate(decision, security_rules)

    result.raw_score = decision.score
    result.final_score = decision.score
    result.overall_confidence = decision.confidence
    result.verdict = decision.verdict
    result.hard_rule_triggered = bool(decision.hard_rules)
    result.hard_rule_codes_json = [item.code for item in decision.hard_rules]
    result.summary_reasons_json = decision.summary_reasons
    result.warnings_json = decision.warnings
    result.limitations_json = LIMITATIONS
    result.summary = {
        VerificationVerdict.VERIFIED: (
            "Evidence strongly satisfies the configured SiteProof verification policy."
        ),
        VerificationVerdict.REVIEW_REQUIRED: "Some verification signals require human review.",
        VerificationVerdict.FLAGGED: "Strong contradictory or failing evidence was detected.",
        VerificationVerdict.INCONCLUSIVE: (
            "Insufficient reliable evidence was available for an automatic decision."
        ),
    }[decision.verdict]
    result.diagnostics_json = {
        "availableWeight": score.available_weight,
        "scoreMethod": "weighted normalized signal score; confidence used for gating",
        "confidenceMethod": "configured-weighted mean of available signal confidence",
        "securityGate": {
            "enabled": engine_version == SECURITY_ENGINE_VERSION,
            "scoreAdjusted": False,
            "constraintCodes": [rule.code for rule in security_rules],
            "advancedSignalsRole": "supporting-evidence-only",
        },
    }
    result.calculated_at = utc_now()
    result.processing_status = VerificationProcessingStatus.COMPLETED

    db.execute(
        delete(VerificationSignalResult).where(
            VerificationSignalResult.verification_result_id == result.id
        )
    )
    for signal in signals:
        configured_weight = float(policy.weights[signal.type])
        contribution = float(score.contributions.get(signal.type, 0.0))
        reason_summary = signal.reasons[0] if signal.reasons else signal.status.value
        db.add(
            VerificationSignalResult(
                verification_result_id=result.id,
                signal_type=signal.type,
                status=signal.status,
                score=signal.score,
                confidence=signal.confidence,
                weight=configured_weight,
                weighted_contribution=contribution,
                required=signal.required,
                reason_summary=reason_summary,
                reasons_json=signal.reasons,
                metrics_json=signal.metrics,
                source_algorithm_version=signal.source_algorithm_version,
            )
        )

    action = {
        VerificationVerdict.FLAGGED: "VERIFICATION_FLAGGED",
        VerificationVerdict.INCONCLUSIVE: "VERIFICATION_INCONCLUSIVE",
    }.get(decision.verdict, "VERIFICATION_COMPLETED")
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=actor,
        entity_type="VERIFICATION_RESULT",
        entity_id=result.id,
        action=action,
        metadata={
            "engineVersion": engine_version,
            "policyVersion": policy.version,
            "score": round(decision.score, 2),
            "verdict": decision.verdict.value,
            "hardRules": [item.code for item in decision.hard_rules],
        },
    )
    db.commit()
    db.refresh(result)
    return result


def get_scoped_result(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
) -> VerificationResult | None:
    session = db.get(VerificationSession, session_id)
    if session is None or session.organization_id != current_user.organization_id:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")
    return db.scalar(
        select(VerificationResult)
        .where(
            VerificationResult.session_id == session.id,
            VerificationResult.organization_id == current_user.organization_id,
        )
        .order_by(VerificationResult.created_at.desc())
    )


def signal_rows(db: Session, result_id: uuid.UUID) -> list[VerificationSignalResult]:
    return list(
        db.scalars(
            select(VerificationSignalResult)
            .where(VerificationSignalResult.verification_result_id == result_id)
            .order_by(VerificationSignalResult.signal_type)
        ).all()
    )
