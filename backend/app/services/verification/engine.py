import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.trust import (
    VerificationProcessingStatus,
    VerificationResult,
    VerificationSignalResult,
    VerificationVerdict,
)
from app.models.verification import VerificationSession
from app.services.audit_service import record_audit
from app.services.verification.collectors import collect_signals
from app.services.verification.explanations import build_explanation
from app.services.verification.hard_rules import evaluate_hard_rules
from app.services.verification.policy import ENGINE_VERSION, resolve_policy
from app.services.verification.scoring import (
    calculate_score,
    required_evidence_is_insufficient,
    threshold_verdict,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_result(
    db: Session,
    *,
    session_id: uuid.UUID,
    policy_id,
) -> VerificationResult | None:
    return db.scalar(
        select(VerificationResult)
        .where(
            VerificationResult.session_id == session_id,
            VerificationResult.policy_id == policy_id,
            VerificationResult.engine_version == ENGINE_VERSION,
        )
        .order_by(VerificationResult.calculation_revision.desc())
    )


def _next_revision(db: Session, *, session_id: uuid.UUID, policy_id) -> int:
    current = db.scalar(
        select(func.max(VerificationResult.calculation_revision)).where(
            VerificationResult.session_id == session_id,
            VerificationResult.policy_id == policy_id,
            VerificationResult.engine_version == ENGINE_VERSION,
        )
    )
    return int(current or 0) + 1


def _persist_signals(db: Session, result: VerificationResult, contributions) -> None:
    db.execute(
        delete(VerificationSignalResult).where(
            VerificationSignalResult.verification_result_id == result.id
        )
    )
    for contribution in contributions:
        signal = contribution.signal
        db.add(
            VerificationSignalResult(
                verification_result_id=result.id,
                signal_type=signal.type,
                status=signal.status,
                score=signal.score,
                confidence=signal.confidence,
                configured_weight=contribution.configured_weight,
                effective_weight=contribution.effective_weight,
                weighted_contribution=contribution.contribution,
                required=signal.required,
                reason_summary=signal.reasons[0] if signal.reasons else signal.status.value,
                reasons_json=list(signal.reasons),
                metrics_json=dict(signal.metrics),
                source_algorithm_version=signal.source_algorithm_version,
            )
        )


class VerificationEngine:
    def calculate(
        self,
        db: Session,
        session_id: uuid.UUID,
        *,
        force: bool = False,
        policy_version: str | None = None,
    ) -> VerificationResult:
        session = db.get(VerificationSession, session_id)
        if session is None:
            raise ValueError("Verification session does not exist.")

        policy = resolve_policy(
            db,
            organization_id=session.organization_id,
            version=policy_version,
        )
        current = _latest_result(db, session_id=session.id, policy_id=policy.id)
        if (
            current is not None
            and current.processing_status == VerificationProcessingStatus.COMPLETED
            and not force
        ):
            return current

        if current is not None and not force:
            result = current
        else:
            result = VerificationResult(
                organization_id=session.organization_id,
                inspection_id=session.inspection_id,
                session_id=session.id,
                policy_id=policy.id,
                policy_version=policy.version,
                engine_version=ENGINE_VERSION,
                calculation_revision=_next_revision(
                    db,
                    session_id=session.id,
                    policy_id=policy.id,
                ),
                processing_status=VerificationProcessingStatus.PENDING,
            )
            db.add(result)
            db.flush()

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
        result.calculated_at = None

        record_audit(
            db,
            organization_id=session.organization_id,
            actor_user_id=session.created_by_user_id,
            entity_type="VERIFICATION_SESSION",
            entity_id=session.id,
            action="VERIFICATION_RECALCULATED" if force else "VERIFICATION_STARTED",
            metadata={
                "engineVersion": ENGINE_VERSION,
                "policyVersion": policy.version,
                "revision": result.calculation_revision,
            },
        )

        try:
            signals, waiting = collect_signals(db, session, policy)
            score = calculate_score(signals, policy)
            _persist_signals(db, result, score.contributions)

            if waiting:
                result.processing_status = VerificationProcessingStatus.WAITING_FOR_SIGNALS
                result.summary = (
                    "Verification is waiting for required upstream analysis to finish."
                )
                result.warnings_json = [
                    "No SiteProof score or verdict is emitted until required upstream analysis is terminal."
                ]
                db.commit()
                db.refresh(result)
                return result

            findings = evaluate_hard_rules(signals, policy)
            if required_evidence_is_insufficient(signals):
                verdict = VerificationVerdict.INCONCLUSIVE
            else:
                verdict = threshold_verdict(score.final_score, policy)
                if (
                    verdict == VerificationVerdict.VERIFIED
                    and score.overall_confidence < policy.minimum_required_confidence
                ):
                    verdict = VerificationVerdict.REVIEW_REQUIRED

                severities = {finding.severity for finding in findings}
                if "FLAGGED" in severities:
                    verdict = VerificationVerdict.FLAGGED
                elif (
                    "REVIEW_REQUIRED" in severities
                    and verdict == VerificationVerdict.VERIFIED
                ):
                    verdict = VerificationVerdict.REVIEW_REQUIRED

            summary, reasons, warnings = build_explanation(
                verdict=verdict,
                signals=signals,
                hard_rules=findings,
                overall_confidence=score.overall_confidence,
            )
            result.processing_status = VerificationProcessingStatus.COMPLETED
            result.raw_score = round(score.raw_score, 4)
            result.final_score = round(score.final_score, 4)
            result.verdict = verdict
            result.overall_confidence = round(score.overall_confidence, 6)
            result.hard_rule_triggered = bool(findings)
            result.hard_rule_codes_json = [finding.code for finding in findings]
            result.summary = summary
            result.summary_reasons_json = reasons
            result.warnings_json = warnings
            result.calculated_at = _utc_now()

            action = {
                VerificationVerdict.VERIFIED: "VERIFICATION_COMPLETED",
                VerificationVerdict.REVIEW_REQUIRED: "VERIFICATION_COMPLETED",
                VerificationVerdict.FLAGGED: "VERIFICATION_FLAGGED",
                VerificationVerdict.INCONCLUSIVE: "VERIFICATION_INCONCLUSIVE",
            }[verdict]
            record_audit(
                db,
                organization_id=session.organization_id,
                actor_user_id=session.created_by_user_id,
                entity_type="VERIFICATION_RESULT",
                entity_id=result.id,
                action=action,
                metadata={
                    "engineVersion": ENGINE_VERSION,
                    "policyVersion": policy.version,
                    "score": result.final_score,
                    "verdict": verdict.value,
                    "hardRules": result.hard_rule_codes_json,
                },
            )
            db.commit()
            db.refresh(result)
            return result
        except Exception:
            db.rollback()
            raise
