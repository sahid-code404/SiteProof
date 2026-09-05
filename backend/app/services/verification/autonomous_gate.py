from __future__ import annotations

import string
import uuid
from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.autonomous_verification import AutonomousAnalysisStatus
from app.models.trust import VerificationVerdict
from app.services.autonomous_verification_service import get_autonomous_result
from app.services.verification.domain import EngineDecision, HardRuleResult


_SHA256_HEX = frozenset(string.hexdigits)


def _is_sha256(value: object) -> bool:
    text = value.strip() if isinstance(value, str) else ""
    return len(text) == 64 and all(character in _SHA256_HEX for character in text)


def semantic_consensus_ready(primary_model: str | None, secondary_model: str | None) -> bool:
    """Require two distinctly configured semantic observers for unattended approval.

    This does not claim the providers are statistically independent, but it prevents the
    autonomous gate from treating a single VLM invocation (or the same model configured twice)
    as sufficient consensus for an automatic VERIFIED result.
    """
    primary = (primary_model or "").strip()
    secondary = (secondary_model or "").strip()
    return bool(primary and secondary and primary != secondary)


def frame_hash_diversity(frame_hashes: list[str] | None) -> float:
    """Return exact sampled-frame diversity without interpreting scene semantics.

    Exact duplicate sampled JPEG hashes are a conservative signal for frozen/repeated evidence.
    It is intentionally only used to block unattended approval, never to flag fraud by itself.
    """
    hashes = [item.strip() for item in (frame_hashes or []) if isinstance(item, str) and item.strip()]
    if not hashes:
        return 0.0
    return len(set(hashes)) / len(hashes)


def autonomous_audit_binding_issues(result: object) -> list[str]:
    """Return missing/malformed provenance needed for a defensible autonomous decision.

    Automatic verification must be reproducibly attributable to a frozen assignment, prompt and
    model versions, sampled evidence hashes, and raw model-response hashes. A malformed audit
    chain is not evidence of fraud, so it only blocks unattended approval and sends the result to
    review.
    """
    issues: list[str] = []
    required_text_fields = {
        "analysisVersion": getattr(result, "analysis_version", None),
        "contractVersion": getattr(result, "contract_version", None),
        "contractPromptVersion": getattr(result, "contract_prompt_version", None),
        "visionPromptVersion": getattr(result, "vision_prompt_version", None),
        "compilerModel": getattr(result, "compiler_model", None),
        "primaryVlmModel": getattr(result, "primary_vlm_model", None),
        "secondaryVlmModel": getattr(result, "secondary_vlm_model", None),
    }
    for name, value in required_text_fields.items():
        if not isinstance(value, str) or not value.strip():
            issues.append(f"missing:{name}")

    if not _is_sha256(getattr(result, "contract_source_hash", None)):
        issues.append("invalid:contractSourceHash")

    frame_hashes = getattr(result, "frame_hashes_json", None)
    sampled_count = int(getattr(result, "sampled_frame_count", 0) or 0)
    if not isinstance(frame_hashes, list) or len(frame_hashes) != sampled_count:
        issues.append("invalid:frameHashCount")
    elif any(not _is_sha256(item) for item in frame_hashes):
        issues.append("invalid:frameHash")

    raw_hashes = getattr(result, "raw_response_hashes_json", None)
    if not isinstance(raw_hashes, dict):
        issues.append("missing:rawResponseHashes")
    else:
        for key in ("contract", "primaryVlm", "secondaryVlm"):
            if not _is_sha256(raw_hashes.get(key)):
                issues.append(f"invalid:rawResponseHash:{key}")

    if not isinstance(getattr(result, "contract_json", None), dict) or not getattr(
        result, "contract_json", None
    ):
        issues.append("missing:contract")
    if not isinstance(getattr(result, "observations_json", None), dict) or not getattr(
        result, "observations_json", None
    ):
        issues.append("missing:observations")
    if getattr(result, "analyzed_at", None) is None:
        issues.append("missing:analyzedAt")

    return issues


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

    if not semantic_consensus_ready(result.primary_vlm_model, result.secondary_vlm_model):
        rules.append(
            HardRuleResult(
                code="AUTONOMOUS_TWO_MODEL_CONSENSUS_REQUIRED",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="Automatic approval requires two differently configured semantic vision models to agree on the critical evidence.",
            )
        )

    audit_issues = autonomous_audit_binding_issues(result)
    if audit_issues:
        rules.append(
            HardRuleResult(
                code="AUTONOMOUS_AUDIT_BINDING_INCOMPLETE",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="The semantic decision provenance is incomplete or malformed; unattended approval is blocked.",
            )
        )

    minimum_frame_count = min(8, max(4, settings.autonomous_frame_count))
    if result.sampled_frame_count < minimum_frame_count:
        rules.append(
            HardRuleResult(
                code="AUTONOMOUS_TEMPORAL_COVERAGE_INSUFFICIENT",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="Too few independently sampled video moments were available for unattended semantic approval.",
            )
        )

    diversity = frame_hash_diversity(result.frame_hashes_json)
    if result.sampled_frame_count >= 4 and diversity < 0.50:
        rules.append(
            HardRuleResult(
                code="AUTONOMOUS_FRAME_DIVERSITY_INSUFFICIENT",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="Too many sampled video frames were exact repeats; a reviewer must confirm the capture is not frozen or replayed.",
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
    audit_issues = autonomous_audit_binding_issues(result)
    return {
        "enabled": True,
        "status": result.status.value,
        "analysisVersion": result.analysis_version,
        "contractVersion": result.contract_version,
        "contractConfidence": result.contract_confidence,
        "compilerModel": result.compiler_model,
        "primaryVlmModel": result.primary_vlm_model,
        "secondaryVlmModel": result.secondary_vlm_model,
        "semanticConsensusReady": semantic_consensus_ready(
            result.primary_vlm_model,
            result.secondary_vlm_model,
        ),
        "auditBindingReady": not audit_issues,
        "auditBindingIssues": audit_issues,
        "sampledFrameCount": result.sampled_frame_count,
        "frameHashDiversity": frame_hash_diversity(result.frame_hashes_json),
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
