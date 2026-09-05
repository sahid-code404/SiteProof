from __future__ import annotations

import uuid
from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.advanced_security import (
    AdvancedProcessStatus,
    AdvancedSecurityResult,
    LocationRiskResult,
    ReplayRiskResult,
    RiskLevel,
)
from app.models.advanced_signals import AdvancedSignalResult
from app.models.trust import VerificationVerdict
from app.services.advanced_security_service import ANALYSIS_VERSION as SECURITY_ANALYSIS_VERSION
from app.services.advanced_signals_service import ANALYSIS_VERSION as SIGNALS_ANALYSIS_VERSION
from app.services.verification.domain import EngineDecision, HardRuleResult
from app.services.verification.versions import (
    AUTONOMOUS_ENGINE_VERSION,
    LEGACY_ENGINE_VERSION,
    SECURITY_ENGINE_VERSION,
)


def security_pipeline_ready(db: Session, session_id: uuid.UUID) -> bool:
    security = db.scalar(
        select(AdvancedSecurityResult).where(
            AdvancedSecurityResult.session_id == session_id,
            AdvancedSecurityResult.algorithm_version == SECURITY_ANALYSIS_VERSION,
            AdvancedSecurityResult.process_status == AdvancedProcessStatus.COMPLETE,
        )
    )
    signals = db.scalar(
        select(AdvancedSignalResult).where(
            AdvancedSignalResult.session_id == session_id,
            AdvancedSignalResult.algorithm_version == SIGNALS_ANALYSIS_VERSION,
            AdvancedSignalResult.process_status == "COMPLETE",
        )
    )
    return security is not None and signals is not None


def engine_version_for_session(db: Session, session_id: uuid.UUID) -> str:
    if not security_pipeline_ready(db, session_id):
        return LEGACY_ENGINE_VERSION
    if get_settings().autonomous_verification_enabled:
        return AUTONOMOUS_ENGINE_VERSION
    return SECURITY_ENGINE_VERSION


def evaluate_security_gate(db: Session, session_id: uuid.UUID) -> list[HardRuleResult]:
    """Return only high-confidence constraints; do not blend security heuristics into the score.

    Deterministic evidence reuse, Android mock-location flags and provider-backed integrity
    failures can hard-flag a result. Strong but heuristic replay/location risk can only cap a
    VERIFIED result to REVIEW_REQUIRED. Phase 10 environment/statistical signals remain
    supporting evidence and never independently change the automated verdict.
    """
    security = db.scalar(
        select(AdvancedSecurityResult).where(
            AdvancedSecurityResult.session_id == session_id,
            AdvancedSecurityResult.algorithm_version == SECURITY_ANALYSIS_VERSION,
            AdvancedSecurityResult.process_status == AdvancedProcessStatus.COMPLETE,
        )
    )
    if security is None:
        return []

    codes = set(security.reason_codes_json or [])
    rules: list[HardRuleResult] = []

    if "EXACT_EVIDENCE_REUSE" in codes or security.evidence_reuse_score >= 0.99:
        rules.append(
            HardRuleResult(
                code="SECURITY_EXACT_EVIDENCE_REUSE",
                maximum_verdict=VerificationVerdict.FLAGGED,
                explanation="Exact verified video and sensor evidence was reused across sessions.",
            )
        )
    elif "EXACT_VIDEO_REUSE" in codes and security.evidence_reuse_score >= 0.80:
        rules.append(
            HardRuleResult(
                code="SECURITY_EXACT_VIDEO_REUSE",
                maximum_verdict=VerificationVerdict.FLAGGED,
                explanation="The exact verified live-capture video appeared in another session.",
            )
        )

    location = db.scalar(
        select(LocationRiskResult).where(
            LocationRiskResult.session_id == session_id,
            LocationRiskResult.algorithm_version == "location-risk-v1",
        )
    )
    if location is not None and location.mock_location_detected and location.confidence >= 0.95:
        rules.append(
            HardRuleResult(
                code="SECURITY_MOCK_LOCATION_DETECTED",
                maximum_verdict=VerificationVerdict.FLAGGED,
                explanation="Android marked captured location evidence as mock-provided.",
            )
        )
    elif (
        location is not None
        and location.risk_level == RiskLevel.HIGH
        and location.confidence >= 0.90
    ):
        rules.append(
            HardRuleResult(
                code="SECURITY_HIGH_LOCATION_RISK",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="High-confidence location behavior requires human review.",
            )
        )

    if (
        "PROVIDER_DEVICE_INTEGRITY_FAILED" in codes
        and security.device_integrity_status == "FAIL"
        and security.device_risk_score >= 0.95
    ):
        rules.append(
            HardRuleResult(
                code="SECURITY_PROVIDER_INTEGRITY_FAILED",
                maximum_verdict=VerificationVerdict.FLAGGED,
                explanation="Provider-backed application or device integrity validation failed.",
            )
        )

    replay = db.scalar(
        select(ReplayRiskResult).where(
            ReplayRiskResult.session_id == session_id,
            ReplayRiskResult.algorithm_version == "replay-risk-v1",
        )
    )
    if (
        replay is not None
        and replay.risk_level == RiskLevel.HIGH
        and replay.score >= 0.90
        and replay.confidence >= 0.90
    ):
        rules.append(
            HardRuleResult(
                code="SECURITY_HIGH_REPLAY_RISK",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="High-confidence replay indicators require human review.",
            )
        )

    if (
        security.overall_risk == RiskLevel.HIGH
        and security.confidence >= 0.90
        and not any(rule.maximum_verdict == VerificationVerdict.FLAGGED for rule in rules)
        and not any(rule.code == "SECURITY_HIGH_REPLAY_RISK" for rule in rules)
        and not any(rule.code == "SECURITY_HIGH_LOCATION_RISK" for rule in rules)
    ):
        rules.append(
            HardRuleResult(
                code="SECURITY_HIGH_COMPOSITE_RISK",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="High-confidence composite anti-spoofing risk requires human review.",
            )
        )

    return list({rule.code: rule for rule in rules}.values())


def apply_security_gate(decision: EngineDecision, rules: list[HardRuleResult]) -> EngineDecision:
    if not rules:
        return decision

    verdict = decision.verdict
    if any(rule.maximum_verdict == VerificationVerdict.FLAGGED for rule in rules):
        verdict = VerificationVerdict.FLAGGED
    elif verdict == VerificationVerdict.VERIFIED:
        verdict = VerificationVerdict.REVIEW_REQUIRED

    merged_rules = list({rule.code: rule for rule in decision.hard_rules + rules}.values())
    security_reasons = [rule.explanation for rule in rules]
    warnings = list(decision.warnings)
    if verdict == VerificationVerdict.REVIEW_REQUIRED:
        warnings = (warnings + security_reasons)[:8]

    return replace(
        decision,
        verdict=verdict,
        hard_rules=merged_rules,
        summary_reasons=(security_reasons + decision.summary_reasons)[:8],
        warnings=warnings,
    )
