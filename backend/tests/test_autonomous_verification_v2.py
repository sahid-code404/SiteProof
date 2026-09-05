from app.models.trust import VerificationVerdict
from app.services.autonomous_ai_client import AIJsonResponse
from app.services.autonomous_verification_service import _aggregate_analysis, _fallback_contract
from app.services.verification.autonomous_gate import apply_autonomous_gate
from app.services.verification.domain import EngineDecision, HardRuleResult


def _verified_decision() -> EngineDecision:
    return EngineDecision(
        score=96.0,
        confidence=0.94,
        verdict=VerificationVerdict.VERIFIED,
        hard_rules=[],
        summary_reasons=["Deterministic evidence passed."],
        warnings=[],
    )


def test_autonomous_review_rule_can_only_downgrade_verified():
    result = apply_autonomous_gate(
        _verified_decision(),
        [
            HardRuleResult(
                code="MANDATORY_EVIDENCE_NOT_PROVEN",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="Mandatory evidence was not proven.",
            )
        ],
    )
    assert result.verdict == VerificationVerdict.REVIEW_REQUIRED
    assert result.score == 96.0


def test_autonomous_flag_rule_overrides_high_deterministic_score():
    result = apply_autonomous_gate(
        _verified_decision(),
        [
            HardRuleResult(
                code="HIGH_CONFIDENCE_TASK_CONTENT_MISMATCH",
                maximum_verdict=VerificationVerdict.FLAGGED,
                explanation="Video shows the wrong task.",
            )
        ],
    )
    assert result.verdict == VerificationVerdict.FLAGGED
    assert result.score == 96.0


def test_autonomous_unavailable_fails_closed_to_inconclusive():
    result = apply_autonomous_gate(
        _verified_decision(),
        [
            HardRuleResult(
                code="AUTONOMOUS_ANALYSIS_UNAVAILABLE",
                maximum_verdict=VerificationVerdict.INCONCLUSIVE,
                explanation="Semantic analysis was unavailable.",
            )
        ],
    )
    assert result.verdict == VerificationVerdict.INCONCLUSIVE


def test_autonomous_gate_never_upgrades_existing_flagged_decision():
    base = _verified_decision()
    base = EngineDecision(
        score=base.score,
        confidence=base.confidence,
        verdict=VerificationVerdict.FLAGGED,
        hard_rules=base.hard_rules,
        summary_reasons=base.summary_reasons,
        warnings=base.warnings,
    )
    result = apply_autonomous_gate(
        base,
        [
            HardRuleResult(
                code="SEMANTIC_LOOKS_GOOD",
                maximum_verdict=VerificationVerdict.REVIEW_REQUIRED,
                explanation="This must not upgrade anything.",
            )
        ],
    )
    assert result.verdict == VerificationVerdict.FLAGGED


def test_fallback_contract_turns_admin_text_into_mandatory_visual_proof():
    contract = _fallback_contract(
        {
            "title": "Transformer TX-4082",
            "description": "Verify oil leakage repair at the assigned transformer.",
            "instructions": "Show the asset number plate and ground below the transformer.",
            "inspectionType": "UTILITY",
        },
        "contract-test-v1",
    )
    assert contract["contractVersion"] == "contract-test-v1"
    assert len(contract["mandatoryEvidence"]) >= 3
    assert all(item["mandatory"] is True for item in contract["mandatoryEvidence"])
    assert contract["assetIdentity"]["required"] is True
    assert "screen" in " ".join(contract["disallowedSubstitutions"]).lower()


def _vlm_response(
    *,
    task: float,
    coverage: float,
    live: float,
    attack: float,
    requirement_satisfied: bool,
) -> AIJsonResponse:
    return AIJsonResponse(
        model="test-vlm",
        raw_hash="a" * 64,
        payload={
            "taskMatch": {"score": task, "confidence": 0.95, "reason": "task"},
            "assetIdentity": {
                "applicable": False,
                "score": 0.90,
                "confidence": 0.90,
                "reason": "asset",
            },
            "mandatoryEvidence": [
                {
                    "id": "subject",
                    "satisfied": requirement_satisfied,
                    "confidence": 0.95,
                    "frameIndexes": [1, 2],
                    "reason": "requirement",
                }
            ],
            "evidenceCoverage": {
                "score": coverage,
                "confidence": 0.95,
                "reason": "coverage",
            },
            "liveScene": {"score": live, "confidence": 0.95, "reason": "live"},
            "presentationAttack": {
                "score": attack,
                "confidence": 0.95,
                "indicators": [],
                "reason": "attack",
            },
        },
    )


def test_two_model_aggregation_is_conservative_and_disagreement_is_security_signal():
    contract = {
        "mandatoryEvidence": [
            {"id": "subject", "description": "Show assigned subject", "mandatory": True}
        ]
    }
    primary = _vlm_response(
        task=0.96,
        coverage=0.97,
        live=0.95,
        attack=0.05,
        requirement_satisfied=True,
    )
    secondary = _vlm_response(
        task=0.55,
        coverage=0.60,
        live=0.70,
        attack=0.65,
        requirement_satisfied=False,
    )
    result = _aggregate_analysis(contract, primary, secondary)
    assert result["taskMatchScore"] == 0.55
    assert result["presentationAttackScore"] == 0.65
    assert result["modelDisagreement"] is True
    assert result["mandatoryFailures"]
    assert result["evidenceCoverageScore"] == 0.0


def test_missing_mandatory_evidence_cannot_be_hidden_by_high_vlm_coverage_score():
    contract = {
        "mandatoryEvidence": [
            {"id": "subject", "description": "Show assigned subject", "mandatory": True}
        ]
    }
    primary = _vlm_response(
        task=0.99,
        coverage=0.99,
        live=0.99,
        attack=0.01,
        requirement_satisfied=False,
    )
    result = _aggregate_analysis(contract, primary, None)
    assert result["mandatoryFailures"]
    assert result["evidenceCoverageScore"] == 0.0
