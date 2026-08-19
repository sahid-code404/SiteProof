# Project State

Current development branch: **Phase 4 — Active Challenge-Response Engine & Sensor-Based Liveness Verification**

Phase 4 is stacked on `phase3/live-capture`; Phase 3's mandatory physical-device acceptance remains a prerequisite. Automated success must never be described as proof that real CameraX/sensor behavior passed on a phone.

## Phase 4 implementation status

Implemented in code:

- dedicated `verification_challenges` persistence and indexes;
- server-generated ROTATE_LEFT, ROTATE_RIGHT, TILT_UP and TILT_DOWN challenges;
- randomized comfortable target/acceptable angles;
- high-entropy nonce, expiry, one-current-challenge and replay/idempotency protection;
- challenge session states and server-validated state transitions;
- gyroscope integration with rotation-vector orientation cross-check;
- PASS / FAIL / INCONCLUSIVE per-challenge results and explainable metrics;
- controlled inconclusive retry and multiple-failure challenge state;
- challenge audit events without raw sensor logging;
- Android one-at-a-time challenge UI and server-aligned countdown;
- bounded sensor-window extraction from the existing common monotonic timeline;
- Room persistence for the active challenge/current reconnect evidence;
- one continuous CameraX recording through the entire challenge sequence;
- challenge timing/results added to final evidence metadata;
- admin challenge timeline and sensor-derived diagnostic view;
- synthetic/API challenge tests and GitHub CI coverage;
- Phase 4 documentation.

## Acceptance status

**NOT YET ACCEPTED ON REAL HARDWARE.**

`docs/testing.md` deliberately leaves the required Android model/version, real sensor sample rate, legitimate-attempt pass rates, wrong-motion rejection rates and final synchronized evidence observations as `NOT TESTED YET` until a physical phone performs them.

## Security boundary

Phase 4 validates requested **phone movement from sensors**. It does not yet prove that external camera-scene motion matches that movement. A user could theoretically rotate the phone while filming prerecorded content.

Therefore this branch intentionally does not include:

- OpenCV optical flow;
- camera motion estimation;
- feature matching/homography;
- visual-inertial sensor fusion;
- screen/replay detection;
- overall SiteProof trust score;
- final verified/flagged authenticity verdict;
- anomaly-detection ML.

Those remain later phases, with visual motion consistency beginning in Phase 5.

## Source of truth

1. `docs/project-spec.md`
2. `docs/challenge-engine.md`
3. `docs/live-capture.md`
4. `docs/session-lifecycle.md`
5. `docs/api.md`
6. `docs/testing.md`
7. current repository code and actual CI/device results
