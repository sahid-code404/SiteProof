# Phase 7 — Explainable Verification & Trust Engine

Phase 7 converts the independent evidence produced by Phases 1–6 into one deterministic, versioned, explainable SiteProof verification result. It does **not** change the live-capture, challenge, computer-vision or visual–inertial algorithms that produced the source evidence.

The SiteProof score is **confidence derived from multiple independent verification signals under the configured SiteProof verification policy**. It is not legal certainty, a guarantee that evidence is genuine, or proof against every sophisticated attack.

## Pipeline

```text
verification session
  ↓
SignalCollector
  ↓
7 normalized VerificationSignal values
  ↓
policy validation / resolution
  ↓
weighted 0–100 score
  ↓
overall evidence confidence
  ↓
hard contradiction rules
  ↓
VERIFIED | REVIEW_REQUIRED | FLAGGED | INCONCLUSIVE
  ↓
deterministic explanation + persisted signal breakdown
```

The engine version is `verification-engine-v1.0`.

## Input signals

The current engine consumes only evidence already implemented by SiteProof:

| Signal | Current source | Meaning |
| --- | --- | --- |
| `LOCATION` | Phase 3 session location snapshot | How well capture location satisfies the configured geofence, accounting for accuracy |
| `SESSION_TIME` | server session/challenge timing | Whether capture/challenge timing is internally consistent and within the inspection deadline |
| `CHALLENGE_COMPLETION` | Phase 4 | Aggregate randomized challenge outcomes, scores, failures, expiry and retry use |
| `SENSOR_EVIDENCE` | Phase 4 | Gyroscope/rotation-vector quality, agreement and sampling quality |
| `VISUAL_EVIDENCE` | Phase 5 | Visual-motion support, quality, RANSAC support and frame validity |
| `SCENE_CONTINUITY` | Phase 5 | Continuity, duplicate/freeze and invalid-frame evidence |
| `VISUAL_INERTIAL_CONSISTENCY` | Phase 6 | Cross-signal consistency score, confidence and mismatch reasons |

Every signal is tied to one organization, inspection and verification session. Phase 7 never combines evidence across sessions.

## Common signal contract

Each collector emits:

```text
VerificationSignal
  type
  status: PASS | PARTIAL | FAIL | INCONCLUSIVE | UNAVAILABLE
  score: 0.0–1.0
  confidence: 0.0–1.0
  available
  required
  reasons[]
  metrics{}
  source_algorithm_version
```

`score` and `confidence` are intentionally different:

- **score** = how well the evidence satisfies the policy requirement;
- **confidence** = how reliable the evidence is for making that assessment.

A strong numerical signal with poor evidence quality is not treated as equally reliable.

## Default policy

The default system policy is **Infrastructure Field Verification v1.0**:

```text
Location                         15
Session / Time                    5
Random Challenges               20
Sensor Evidence                 15
Visual Evidence                 10
Scene Continuity                10
Visual–Inertial Consistency     25
                                ──
Total                           100
```

The higher fusion weight is intentional: Phase 6 directly compares two independently acquired evidence families, physical motion and camera motion.

Required by the default policy:

```text
LOCATION
SESSION_TIME
CHALLENGE_COMPLETION
SENSOR_EVIDENCE
VISUAL_EVIDENCE
VISUAL_INERTIAL_CONSISTENCY
```

Scene continuity is weighted but optional in v1.0. If an optional signal is unavailable its weight is re-normalized over available evidence. Missing or technically inconclusive **required** evidence prevents automatic verification and yields `INCONCLUSIVE`.

Policies are stored in `verification_policies`. Organization-specific active policies override the system default. Policy validation requires supported signal types, ordered thresholds, valid confidence bounds, valid hard rules and weights totaling exactly 100.

## Score calculation

Signals are normalized before weighting:

```text
contribution = signal.score × effective_weight
raw_score = Σ contribution
```

The numerical score is retained as transparent evidence aggregation. Phase 7 v1.0 does **not** silently lower the score because a hard rule fired:

```text
raw_score == final_score
```

The hard-rule code and final verdict show the policy constraint explicitly.

Overall confidence is the effective-weighted mean of available signal confidences. Confidence is **not multiplied into the numerical score** in v1.0. Instead, it is a verdict gate. Automatic `VERIFIED` requires overall confidence of at least `0.70` under the default policy.

## Threshold verdicts

Default thresholds:

```text
85.00–100.00 → VERIFIED
65.00–84.99  → REVIEW_REQUIRED
0.00–64.99   → FLAGGED
```

Required evidence that is unavailable/inconclusive produces `INCONCLUSIVE`, regardless of the weighted total.

## Hard contradiction rules

Weighted averages cannot be allowed to hide serious contradictions. Hard rules are evaluated separately from scoring.

### High-confidence fusion mismatch

If any Phase 6 mismatch has confidence `>= 0.80`, automatic `VERIFIED` is blocked and the default policy returns `FLAGGED` with `HIGH_CONFIDENCE_FUSION_MISMATCH`.

### High-confidence wrong location

A clearly outside-radius location with confidence `>= 0.80` triggers `HIGH_CONFIDENCE_WRONG_LOCATION`. The location collector treats unusably poor GPS as `INCONCLUSIVE`, not fraud.

### Multiple high-confidence challenge failures

Two or more randomized challenge failures whose Phase 4 sensor confidence is `>= 0.80` trigger `MULTIPLE_HIGH_CONFIDENCE_CHALLENGE_FAILURES`.

### Major scene discontinuity

Minimum scene-continuity score `<= 0.40` with confidence `>= 0.80` triggers at least human review with `MAJOR_SCENE_DISCONTINUITY`.

These rules are typed policy configuration, not duplicated magic numbers throughout the engine.

## Deterministic explanations

No LLM participates in scoring or verdict selection. The explanation builder orders information as serious policy issues, mandatory evidence limitations, partial warnings, positive supporting evidence, and limitations.

The UI intentionally uses `FLAGGED`, `REVIEW REQUIRED`, `INCONCLUSIVE`, `SUSPICIOUS SIGNAL` and `CONSISTENCY MISMATCH` terminology instead of “fake”, “fraud” or “attacker”.

## Persistence and versioning

Migration `0007_phase7_verification_engine` adds:

- `verification_policies`
- `verification_results`
- `verification_signal_results`
- `review_decisions`

A verification result stores organization/inspection/session identity, policy id/version, engine version, calculation revision, score, confidence, verdict, hard-rule codes and deterministic explanations. Per-signal rows store normalized score/confidence, configured/effective weight, weighted contribution, required status, reasons, metrics and source algorithm version.

Calculation identity is version-aware and idempotent for the same session + policy + engine version. An authorized forced recalculation creates a new `calculation_revision`; historical results are not overwritten. A new policy version creates a new policy-bound result.

## Automatic processing

```text
verified evidence upload
  → Phase 5 visual analysis
  → Phase 6 visual–inertial analysis
  → Phase 7 VerificationEngine
```

If upstream Phase 5/6 evidence is still processing, the result uses `WAITING_FOR_SIGNALS` and emits no premature score/verdict. Forced Phase 5 or Phase 6 retry also forces a new Phase 7 calculation revision after the upstream result changes.

## API and access control

```text
GET  /api/v1/sessions/{sessionId}/verification
POST /api/v1/sessions/{sessionId}/verification/recalculate   # ADMIN
POST /api/v1/inspections/{inspectionId}/review               # ADMIN/REVIEWER
```

Human review decisions are `APPROVED`, `REJECTED`, or `RECAPTURE_REQUIRED` and remain distinct from the automated verdict. The current prototype deliberately does not overwrite the inspection lifecycle state from a review decision; the review event/result is authoritative for the operational decision until a later workflow phase defines final state transitions.

Inspectors may retrieve the verification resource only for their own session, but receive a simplified operational message. Detailed score, confidence, per-signal breakdown and hard-rule diagnostics are withheld from the inspector UI.

## Reviewer UI

The inspection detail page now contains a top-level Phase 7 report with score, automated verdict, overall confidence, policy/engine version, signal contribution breakdown, hard-rule override notice, deterministic explanation/warnings, latest human review, review controls, and admin recalculation. Existing Phase 4 sensor, Phase 5 camera and Phase 6 cross-signal panels remain the evidence drill-down below it.

## Viva example

Hypothetical math only:

```text
Location           0.95 × 15 = 14.25
Session / Time     0.98 ×  5 =  4.90
Challenges         0.94 × 20 = 18.80
Sensors            0.90 × 15 = 13.50
Visual             0.88 × 10 =  8.80
Continuity         0.92 × 10 =  9.20
Fusion             0.93 × 25 = 23.25
                              ─────
                              92.70
```

If overall confidence meets the policy minimum and no hard rule fires, the threshold verdict is `VERIFIED`. These values explain the math only; they are not claimed SiteProof measurements.

## Calibration and limitations

Current v1.0 weights/thresholds are defensible prototype policy defaults, not empirically calibrated production values. They must be evaluated against real Phase 4–6 sessions: legitimate, low-quality, controlled mismatch/replay, and wrong-location/blocked-location behavior. Thresholds should be changed only from measured evidence, never to force a desired demo verdict.

Residual limitations include phone hardware quality, GPS uncertainty, low light/texture, camera/sensor latency, synchronized or instrumented attacks, upstream algorithm errors and policy sensitivity. SiteProof should support human judgment in high-risk cases rather than replace it.

## Phase boundary

Phase 7 intentionally does **not** implement server signing keys, signed receipts, canonical signed verification manifests, C2PA, Play Integrity scoring, Wi-Fi scoring, advanced replay classification or anomaly-detection ML.

Those remain Phase 8 and later. Phase 7 must not be called accepted until at least one real Android SiteProof session reaches a reproducible score/verdict and the required controlled evidence scenarios are recorded.
