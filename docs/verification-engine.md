# Phase 7 — Explainable Verification & Trust Engine

Phase 7 combines the already-produced Phase 1–6 evidence into one deterministic, explainable SiteProof verification result. It does not digitally sign that result and does not introduce new device-integrity, Wi-Fi, replay-classification, or ML signals.

## Security meaning

A SiteProof score is **confidence derived from multiple independent verification signals under the configured SiteProof verification policy**. It is not a claim of legal certainty, 100% authenticity, or impossibility of spoofing.

Automated verdicts are deliberately worded as `VERIFIED`, `REVIEW_REQUIRED`, `FLAGGED`, or `INCONCLUSIVE`. SiteProof does not automatically label a person or submission `FAKE`, `FRAUD`, or `ATTACKER`.

## Pipeline

```text
verification session
  ↓
SignalCollector
  ↓
normalized VerificationSignal values (0..1 score + separate confidence)
  ↓
PolicyResolver
  ↓
ScoreCalculator
  ↓
HardRuleEvaluator
  ↓
VerdictResolver
  ↓
ExplanationBuilder
  ↓
versioned VerificationResult + VerificationSignalResult rows
```

The engine version is `verification-engine-v1.0`.

## Current signal model

Every signal carries:

```text
type
status: PASS | PARTIAL | FAIL | INCONCLUSIVE | UNAVAILABLE
score: 0.0..1.0
confidence: 0.0..1.0
available
required
reasons
metrics
source algorithm version
```

Score answers **how well the evidence satisfied the verification requirement**. Confidence answers **how reliable the evidence was for making that assessment**. Those concepts are not merged into one opaque value.

Current Phase 7 signal types are:

```text
LOCATION
SESSION_TIME
CHALLENGE_COMPLETION
SENSOR_QUALITY
VISUAL_MOTION
SCENE_CONTINUITY
VISUAL_INERTIAL_CONSISTENCY
```

## Default policy

Default organization policy:

```text
Infrastructure Field Verification
Policy version 1.0
```

Weights:

```text
Location                         15
Session / Time                    5
Random Challenges                20
Sensor Evidence                  15
Visual Evidence                  10
Scene Continuity                 10
Visual–Inertial Consistency      25
                                ───
Total                            100
```

Visual–inertial consistency has the largest single weight because it directly compares two independently acquired evidence families: physical phone motion and camera motion.

Required signals in the prototype policy:

```text
LOCATION
CHALLENGE_COMPLETION
SENSOR_QUALITY
VISUAL_MOTION
VISUAL_INERTIAL_CONSISTENCY
```

`SESSION_TIME` and `SCENE_CONTINUITY` are supporting signals in the initial policy. If an optional signal is unavailable its weight is re-normalized across the available evidence. An unavailable or technically inconclusive required signal does **not** become zero-score fraud evidence; the verdict becomes `INCONCLUSIVE`.

## Score calculation

Each available signal contribution is:

```text
normalized signal score × configured weight
```

If optional signals are unavailable, available weights are safely re-normalized back to 100. Required-signal completeness is checked independently.

The engine intentionally does **not** blindly multiply each score by confidence. That can make otherwise valid scores artificially small and difficult to interpret. Instead:

- the numerical score measures policy satisfaction;
- `overall_confidence` is the configured-weighted mean reliability of available signals;
- automatic `VERIFIED` requires sufficient overall confidence.

Default thresholds:

```text
85–100   VERIFIED
65–84    REVIEW_REQUIRED
0–64     FLAGGED
```

Automatic `VERIFIED` also requires overall confidence >= 0.70 and no blocking hard rule.

Internally the score keeps floating-point precision. The reviewer UI rounds only for display.

### Viva example

Illustrative values only:

```text
Location       0.95 × 15 = 14.25
Challenges     0.94 × 20 = 18.80
Sensors        0.90 × 15 = 13.50
Visual         0.88 × 10 =  8.80
Continuity     0.92 × 10 =  9.20
Fusion         0.93 × 25 = 23.25
Session/time   0.92 ×  5 =  4.60
                            ─────
                            92.40
```

With sufficient confidence and no hard rule, this would resolve to `VERIFIED`. These numbers are an explanation example, not measured project results.

## Hard rules

Weighted scoring and verdict constraints are separate. Hard rules do not secretly rewrite the score. A result can therefore retain, for example, a score of 88 while a strong contradiction blocks `VERIFIED`.

Current hard-rule codes:

```text
HIGH_CONFIDENCE_FUSION_MISMATCH
CLEAR_WRONG_LOCATION
MULTIPLE_HIGH_CONFIDENCE_CHALLENGE_FAILURES
MAJOR_SCENE_DISCONTINUITY
```

Semantics:

- high-confidence Phase 6 `MISMATCH` prevents automatic verification and resolves to `FLAGGED`;
- clearly outside high-confidence location evidence resolves to `FLAGGED`;
- two or more high-confidence randomized challenge failures resolve to `FLAGGED`;
- a high-confidence major scene discontinuity prevents automatic verification and requires at least human review.

A hard rule is an explainable verdict constraint, not an extra hidden score.

## Signal collection

### Location

Uses the persisted capture-start distance, assigned radius, and reported accuracy. Clearly outside high-confidence evidence fails. Boundary uncertainty is partial. Unusably poor GPS is `INCONCLUSIVE` rather than definitive location failure.

### Session / time

Uses server-recorded capture start/end, inspection deadline, monotonic ordering, and existing client/server clock-offset evidence.

### Challenge completion

Uses the latest Phase 4 attempt for each sequence, per-challenge validation scores, sensor confidence, explicit failures/inconclusive outcomes, and retry usage.

### Sensor evidence

Uses Phase 4 sensor score and gyroscope window quality. Magnetometer availability is not treated as a required proof signal.

### Visual evidence

Uses current-version Phase 5 terminal results, successful challenge coverage, visual confidence, and RANSAC support.

### Scene continuity

Uses Phase 5 scene-continuity score, duplicate-frame ratio, invalid-frame ratio, and freeze duration. It remains a distinct supporting signal in the initial policy.

### Visual–inertial consistency

Uses current-version Phase 6 consistency status, effective consistency score, fusion confidence, and structured mismatch reasons. Low-quality or unfinished fusion is not converted into an accusation.

## Persistence and reproducibility

Migration `0007_phase7_verification` adds:

```text
verification_policies
verification_results
verification_signal_results
review_decisions
```

A verification result is uniquely identified for idempotency by:

```text
session_id + policy_id + policy_version + engine_version
```

The same current policy/engine retry returns the current deterministic result instead of creating duplicates. Future policy or engine versions create traceable historical results rather than silently overwriting old versions.

Stored result information includes policy name/version, engine version, score, confidence, verdict, hard-rule codes, deterministic explanations/warnings, limitations, and per-signal contributions.

## APIs

```text
GET  /api/v1/sessions/{sessionId}/verification
POST /api/v1/sessions/{sessionId}/verification/recalculate
POST /api/v1/inspections/{inspectionId}/review
```

`ADMIN` and `REVIEWER` may see the detailed signal breakdown and policy-rule diagnostics. Inspectors may see the simpler session result but detailed security diagnostics are omitted. Recalculation is admin-only.

## Automated verdict vs human decision

These are independent records.

```text
Automated verdict: REVIEW_REQUIRED
Human decision:    APPROVED
```

Reviewer decisions are:

```text
APPROVED
REJECTED
RECAPTURE_REQUIRED
```

A reason is required for rejection or recapture. The automated result is preserved and is never replaced by a reviewer decision.

## Reviewer report

The inspection detail page shows the Phase 7 report before low-level evidence drill-down:

- SiteProof score `/100`;
- automated verdict and precise explanatory banner;
- overall confidence;
- policy and engine version;
- signal contribution / configured weight;
- signal confidence and status;
- hard-rule override callout;
- deterministic reasons, warnings, and limitations;
- separate human review controls.

The existing Phase 4 sensor, Phase 5 visual, and Phase 6 fusion panels remain the technical drill-down rather than being duplicated into the report summary.

## Audit events

Current Phase 7 flow records:

```text
VERIFICATION_STARTED
VERIFICATION_COMPLETED
VERIFICATION_FLAGGED
VERIFICATION_INCONCLUSIVE
REVIEW_APPROVED
REVIEW_REJECTED
RECAPTURE_REQUESTED
```

Metadata includes engine/policy version and compact verdict/score fields rather than giant diagnostics.

## Real-world calibration — pending

No Phase 7 real score is claimed yet. Required real acceptance still includes:

```text
Genuine Android end-to-end session:            NOT TESTED YET
Controlled basic replay/mismatch session:       NOT TESTED YET
Controlled wrong-location session:              NOT TESTED YET
Poor-quality/obstructed-camera session:          NOT TESTED YET
Real score/confidence distributions:             NOT TESTED YET
Threshold sensitivity using measured sessions:   NOT TESTED YET
Trust-engine processing time on real evidence:   NOT TESTED YET
```

Real results must be recorded as observed. Thresholds must not be changed merely to force a desired demo verdict.

## Limitations

The score:

- is not legal certainty;
- is not proof against every sophisticated attack;
- depends on phone hardware, scene quality, and upstream algorithms;
- depends on the configured policy;
- can be inconclusive;
- should support rather than replace human judgment in high-risk cases.

Phase 7 does not add Play Integrity, Wi-Fi environment scoring, a final replay classifier, ML anomaly detection, signed receipts, cryptographic report sealing, C2PA, or a private signing key.

## Phase 8 boundary

Phase 7 stops after producing a stable, versioned:

```text
verification result
score
verdict
signal breakdown
policy version
engine version
```

Cryptographically sealing that result is Phase 8 and is intentionally not implemented here.
