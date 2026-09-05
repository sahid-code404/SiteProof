from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.autonomous_verification import AutonomousAnalysisStatus
from app.models.trust import VerificationVerdict
from app.services.autonomous_verification_service import get_autonomous_result
from app.services.verification.domain import EngineDecision, HardRuleResult


def evaluate_autonomous_gate(db: Session, session_id: uuid.UUID) -> list[HardRuleResult]:
    """Convert AI observations into one-way constraints on the deterministic verdict.

    The autonomous layer is deliberately asymmetric: it may block or downgrade automatic
    approval, but it can never upgrade REVIEW_REQUIRED/FLAGGED/INCONCLUSIVE to VERIFIED.
    """
    settings = get_settings()
    if not settings.autonomous_verification_enabled:
        return []

    result = get_autonomous_result(db, session_id)
    if result is None or result.status in {
        AutonomousAnalysisStatus.PENDING,
        AutonomousAnalysisStatus.PROCESSING,
    }:
        return [
            HardRuleResult(
                code="AUTONOMOUS_ANALYSIS_PENDING",
                maximum_verdict=VerificationVerdict.INCONCLUSIVE,
                explanation="Semantic evidence analysis has not completed; automatic approval is blocked.",
            )
        ]
    if result.status in {AutonomousAnalysisStatus.UNAVAILABLE, AutonomousAnalysisStatus.FAILED}:
        return [
            HardRuleResult(
                code="AUTONOMOUS_ANALYSIS_UNAVAILABLE",
                maximum_verdict=VerificationVerdict.INCONCLUSIVE,
                explanation="Required semantic video verification was unavailable; automatic approval is blocked.",
            )
        ]

    rules: list[HardRuleResult] = []
    hard_conf = settings.autonomous_hard_flag_confidence

    if result.contract_confidence < 0.65:
        rules.append(
            HardRuleResult(
                code="AUTONOMOUS_CONTRACT_LOW_CONFIDENCE",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="The natural-language inspection contract could not be interpreted with enough confidence for unattended approval.",
            )
        )

    task_score = result.task_match_score or 0.0
    task_conf = result.task_match_confidence or 0.0
    if task_score <= settings.autonomous_task_mismatch_threshold and task_conf >= hard_conf:
        rules.append(
            HardRuleResult(
                code="HIGH_CONFIDENCE_TASK_CONTENT_MISMATCH",
                maximum_verdict=VerificationVerdict.FLAGGED,
                explanation="High-confidence semantic analysis found that the video does not show the assigned inspection task.",
            )
        )
    elif task_score < settings.autonomous_review_task_threshold or task_conf < 0.75:
        rules.append(
            HardRuleResult(
                code="TASK_CONTENT_NOT_STRONGLY_PROVEN",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="The video did not prove the assigned task strongly enough for automatic approval.",
            )
        )

    asset_contract = (result.contract_json or {}).get("assetIdentity") or {}
    identity_required = bool(asset_contract.get("required"))
    asset_score = result.asset_identity_score or 0.0
    asset_conf = result.asset_identity_confidence or 0.0
    if identity_required:
        if asset_score <= settings.autonomous_asset_mismatch_threshold and asset_conf >= hard_conf:
            rules.append(
                HardRuleResult(
                    code="HIGH_CONFIDENCE_ASSET_IDENTITY_MISMATCH",
                    maximum_verdict=VerificationVerdict.FLAGGED,
                    explanation="The captured asset strongly appears to be different from the assigned asset.",
                )
            )
        elif asset_score < 0.75 or asset_conf < 0.75:
            rules.append(
                HardRuleResult(
                    code="ASSET_IDENTITY_NOT_STRONGLY_PROVEN",
                    maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                    explanation="Identity evidence was insufficient to prove this is the assigned physical asset.",
                )
            )

    coverage = result.evidence_coverage_score or 0.0
    coverage_conf = result.evidence_coverage_confidence or 0.0
    if result.mandatory_failures_json:
        rules.append(
            HardRuleResult(
                code="MANDATORY_EVIDENCE_NOT_PROVEN",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="One or more mandatory evidence requirements derived from the admin description were not proven.",
            )
        )
    if coverage < settings.autonomous_min_coverage or coverage_conf < 0.70:
        rules.append(
            HardRuleResult(
                code="INSUFFICIENT_SEMANTIC_COVERAGE",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="The capture did not cover enough of the required inspection evidence for unattended approval.",
            )
        )

    attack_score = result.presentation_attack_score or 0.0
    attack_conf = result.presentation_attack_confidence or 0.0
    if (
        attack_score >= settings.autonomous_presentation_attack_flag_threshold
        and attack_conf >= hard_conf
    ):
        rules.append(
            HardRuleResult(
                code="HIGH_CONFIDENCE_PRESENTATION_ATTACK",
                maximum_verdict=VerificationVerdict.FLAGGED,
                explanation="High-confidence visual evidence indicates a screen, photograph, print, or other presentation/replay attack.",
            )
        )
    elif attack_score >= 0.55 and attack_conf >= 0.75:
        rules.append(
            HardRuleResult(
                code="PRESENTATION_ATTACK_SUSPECTED",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="Possible screen/photo/replay presentation indicators require human review.",
            )
        )

    live_score = result.live_scene_score or 0.0
    live_conf = result.live_scene_confidence or 0.0
    if live_score <= 0.25 and live_conf >= hard_conf:
        rules.append(
            HardRuleResult(
                code="HIGH_CONFIDENCE_NON_LIVE_SCENE",
                maximum_verdict=VerificationVerdict.FLAGGED,
                explanation="High-confidence semantic evidence is inconsistent with a live physical scene.",
            )
        )
    elif live_score < settings.autonomous_live_scene_review_threshold or live_conf < 0.70:
        rules.append(
            HardRuleResult(
                code="LIVE_SCENE_NOT_STRONGLY_PROVEN",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="A live physical scene was not established strongly enough for automatic approval.",
            )
        )

    if result.model_disagreement:
        rules.append(
            HardRuleResult(
                code="AUTONOMOUS_MODEL_DISAGREEMENT",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="Independent semantic models disagreed on critical evidence; human review is required.",
            )
        )

    return list({rule.code: rule for rule in rules}.values())


def apply_autonomous_gate(
    decision: EngineDecision,
    rules: list[HardRuleResult],
) -> EngineDecision:
    if not rules:
        return decision

    verdict = decision.verdict
    if any(rule.maximum_verdict == VerificationVerdict.FLAGGED for rule in rules):
        verdict = VerificationVerdict.FLAGGED
    elif verdict != VerificationVerdict.FLAGGED and any(
        rule.maximum_verdict == VerificationVerdict.INCONCLUSIVE for rule in rules
    ):
        verdict = VerificationVerdict.INCONCLUSIVE
    elif verdict == VerificationVerdict.VERIFIED:
        verdict = VerificationVerdict.REVIEW_REQUIRED

    merged_rules = list({rule.code: rule for rule in decision.hard_rules + rules}.values())
    reasons = [rule.explanation for rule in rules]
    warnings = list(decision.warnings)
    if verdict in {VerificationVerdict.REVIEW_REQUIRED, VerificationVerdict.INCONCLUSIVE}:
        warnings = (warnings + reasons)[:8]
    return replace(
        decision,
        verdict=verdict,
        hard_rules=merged_rules,
        summary_reasons=(reasons + decision.summary_reasons)[:8],
        warnings=warnings,
    )


def autonomous_diagnostics(db: Session, session_id: uuid.UUID) -> dict[str, Any]:
    settings = get_settings()
    if not settings.autonomous_verification_enabled:
        return {"enabled": False}
    result = get_autonomous_result(db, session_id)
    if result is None:
        return {"enabled": True, "status": "PENDING"}
    return {
        "enabled": True,
        "status": result.status.value,
        "analysisVersion": result.analysis_version,
        "contractVersion": result.contract_version,
        "contractConfidence": result.contract_confidence,
        "compilerModel": result.compiler_model,
        "primaryVlmModel": result.primary_vlm_model,
        "secondaryVlmModel": result.secondary_vlm_model,
        "sampledFrameCount": result.sampled_frame_count,
        "taskMatch": {
            "score": result.task_match_score,
            "confidence": result.task_match_confidence,
        },
        "assetIdentity": {
            "score": result.asset_identity_score,
            "confidence": result.asset_identity_confidence,
        },
        "evidenceCoverage": {
            "score": result.evidence_coverage_score,
            "confidence": result.evidence_coverage_confidence,
        },
        "liveScene": {
            "score": result.live_scene_score,
            "confidence": result.live_scene_confidence,
        },
        "presentationAttack": {
            "score": result.presentation_attack_score,
            "confidence": result.presentation_attack_confidence,
        },
        "mandatoryFailureCount": len(result.mandatory_failures_json or []),
        "mandatoryFailures": result.mandatory_failures_json or [],
        "modelDisagreement": result.model_disagreement,
        "failureReason": result.failure_reason,
    }
