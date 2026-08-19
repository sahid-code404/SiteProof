# Project State

Current development branch: **Phase 6 — Visual–Inertial Sensor Fusion & Cross-Signal Consistency**

Working branch: `phase6-visual-inertial-fusion`

Base: Phase 5 head `f1db48923247993611fe445b147ef5896a164d4f`

Phase 6 extends the existing Phase 4 sensor and Phase 5 visual pipelines; it does not rebuild them.

## Existing inputs

Phase 4 provides backend-derived sensor movement for randomized rotate/tilt challenges:

- gyroscope integrated angle;
- rotation-vector angle delta;
- semantic challenge direction;
- sensor confidence and quality;
- server/client timing metadata;
- complete hashed sensor evidence on the common capture timeline.

Phase 5 provides camera-side visual movement:

- physical-camera semantic direction;
- approximate visual angle;
- movement start/end;
- visual confidence and quality;
- RANSAC/continuity diagnostics;
- visual motion curve on the common session timeline.

## Phase 6 implemented in code

The Phase 6 branch adds:

- a common `MotionEstimate` representation for sensor and vision;
- centralized coordinate/direction normalization;
- secure extraction of the missing high-rate gyroscope timing curve from verified `sensors.ndjson.gz`;
- direction, magnitude, start/end timing and duration comparators;
- independent motion-curve normalization and configurable 20 Hz resampling;
- Pearson correlation plus limited-lag cross-correlation;
- confidence-aware deterministic aggregation;
- `CONSISTENT`, `PARTIALLY_CONSISTENT`, `MISMATCH`, `INCONCLUSIVE` states;
- structured mismatch reasons including opposite direction, visual-without-sensor motion and sensor-without-visual motion;
- `visual_inertial_results` persistence keyed by challenge + `fusion-v1.0`;
- automatic fusion after Phase 5 completes;
- ADMIN/REVIEWER fusion API and reanalysis endpoint;
- reviewer side-by-side sensor/camera comparison and lightweight normalized timeline graph;
- fusion audit events;
- deterministic synthetic and integration tests;
- `docs/visual-inertial-fusion.md`.

## Phase boundary

Phase 6 produces **cross-signal consistency only**.

It does not produce:

- overall SiteProof trust score;
- final `VERIFIED`, `FLAGGED`, `AUTHENTIC`, or `REVIEW REQUIRED` verdict;
- signed final verification report;
- Play Integrity scoring;
- Wi-Fi fingerprint scoring;
- anomaly-detection ML;
- final replay/screen classification.

Those belong to Phase 7 and later.

## Validation state

Automated validation must come from the current Phase 6 GitHub Actions run; do not claim it green until the exact head passes backend, web and Android jobs.

Real-device Phase 6 acceptance is still pending. CI and synthetic evidence cannot satisfy the required genuine-device and controlled-screen experiments.

Required measured work still includes:

- a genuine SiteProof Android challenge producing defensible real sensor/video consistency;
- a controlled video-on-screen scenario producing detectable cross-signal inconsistency where expected;
- legitimate angle-error, timing-offset and correlation distributions;
- threshold tuning from those real measurements;
- device/camera/sensor metadata;
- actual fusion processing time;
- repeated rotate/tilt trials and multiple Android devices where practical.

No real-device or attack result is to be fabricated.

## Source of truth

1. `docs/project-spec.md`
2. `docs/challenge-engine.md`
3. `docs/visual-motion-analysis.md`
4. `docs/visual-inertial-fusion.md`
5. `docs/session-lifecycle.md`
6. `docs/api.md`
7. `docs/testing.md`
8. current repository code and actual CI/device results
