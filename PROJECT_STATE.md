# Project State

Current development branch: **Phase 7 — Explainable Verification & Trust Engine**

Working branch: `phase7-verification-trust-engine`

Base: Phase 6 head `fd1bbaf1b871540e49710b46af4a97980873ea06`

Draft PR: **#6 — Phase 7: explainable verification and trust engine**

## Existing upstream evidence

Phase 7 consumes, but does not rebuild: Phase 3 location/session/capture evidence, Phase 4 randomized challenge + sensor results, Phase 5 camera visual-motion + scene continuity results, and Phase 6 visual–inertial consistency results.

## Phase 7 implemented in code

- common seven-signal `VerificationSignal` abstraction;
- persisted/configurable verification policies with validation;
- default 100-point Infrastructure Field Verification v1.0 policy;
- separate signal score and confidence;
- optional-weight re-normalization;
- required-signal completeness rules;
- deterministic hard contradiction rules;
- `VERIFIED`, `REVIEW_REQUIRED`, `FLAGGED`, `INCONCLUSIVE` verdicts;
- transparent score plus separate policy override codes;
- deterministic non-LLM explanation generation;
- `verification-engine-v1.0` versioning;
- historical calculation revisions rather than overwrite;
- verification result + per-signal breakdown persistence;
- human `APPROVED` / `REJECTED` / `RECAPTURE_REQUIRED` decisions stored separately;
- automatic Phase 6 → Phase 7 processing;
- detailed admin/reviewer API and masked inspector response;
- reviewer score/report/review UI;
- simplified Android inspector verification result refresh;
- Phase 7 unit/integration/web tests;
- `docs/verification-engine.md`.

## Default score policy

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

Thresholds: VERIFIED >=85, REVIEW_REQUIRED >=65, otherwise FLAGGED. Required unavailable/inconclusive evidence yields INCONCLUSIVE. Overall confidence must be >=0.70 for automatic VERIFIED. Hard rules can restrict the verdict without secretly rewriting the score.

## Phase boundary

Phase 7 produces a stable, reproducible score/verdict/signal breakdown **in code**, but does not cryptographically seal it. Server signing keys, signed receipts, canonical signed report/manifest, C2PA, Play Integrity/Wi-Fi scoring, advanced replay classification and anomaly-detection ML belong to Phase 8 and later.

## Automated validation state

Use the latest GitHub Actions run on the exact Phase 7 PR head as the source of truth. Do not copy counts from an earlier commit after the branch changes.

## Real-world acceptance state

**NOT TESTED YET / NOT ACCEPTED YET.**

```text
legitimate full Android → score/verdict:             NOT TESTED YET
controlled basic replay/mismatch → policy behavior:  NOT TESTED YET
wrong-location / geofence-block behavior:            NOT TESTED YET
poor visual evidence → inconclusive/review behavior: NOT TESTED YET
real score/confidence distributions:                 NOT TESTED YET
real trust calculation runtime:                      NOT TESTED YET
```

No real score, false-positive rate, attack result or performance measurement is to be fabricated.

## Phase 8 readiness condition

Phase 8 must not start until Phase 7 has real end-to-end acceptance evidence. At that point SiteProof must have a stable persisted verification result containing score, verdict, signal breakdown, policy version and engine version suitable for later cryptographic sealing.

## Source of truth

1. `docs/project-spec.md`
2. `docs/challenge-engine.md`
3. `docs/visual-motion-analysis.md`
4. `docs/visual-inertial-fusion.md`
5. `docs/verification-engine.md`
6. current repository code
7. actual CI and real-device results
