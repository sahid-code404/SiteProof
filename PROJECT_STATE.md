# Project State

Current development branch: **Phase 4 — Active Challenge-Response Engine & Sensor-Based Liveness Verification**

Phase 4 is stacked on `phase3/live-capture`.

Phase 3 physical-device acceptance: **PASS — completed on 2026-08-19.** A physical Android phone successfully produced real CameraX video, accelerometer, gyroscope, rotation-vector and GPS/location evidence from one live session; the evidence package and manifest uploaded to the backend and appeared in the admin dashboard. Temporary network loss was also tested successfully: evidence remained recoverable and uploaded after connectivity returned.

Phase 4 physical-device acceptance: **PASS — completed on 2026-08-20.** Real-device testing confirmed randomized ROTATE_LEFT, ROTATE_RIGHT, TILT_UP and TILT_DOWN challenges, animated/human-readable movement guidance, live progress feedback, challenge PASS/FAIL/INCONCLUSIVE handling, explicit challenge retry, at least three reattempts per challenge, clean verification retry, upload retry, continuous CameraX capture, synchronized sensor/location evidence, final evidence upload and admin challenge/evidence display. Web location search and browser current-location selection were also confirmed working.

## Phase 4 implementation status

Implemented and physically exercised:

- dedicated `verification_challenges` persistence and indexes;
- server-generated ROTATE_LEFT, ROTATE_RIGHT, TILT_UP and TILT_DOWN challenges;
- randomized comfortable target/acceptable angles;
- high-entropy nonce, expiry, one-current-challenge and replay/idempotency protection;
- challenge session states and server-validated state transitions;
- gyroscope integration with rotation-vector orientation cross-check;
- PASS / FAIL / INCONCLUSIVE per-challenge results and explainable metrics;
- explicit fresh-challenge retry for FAIL / INCONCLUSIVE with at least three reattempts per challenge;
- challenge audit events without raw sensor logging;
- Android animated phone/directional-arrow guidance with human-readable movement instructions;
- live movement feedback (`WAITING`, wrong direction, keep going, good range, too far) without exposing raw validator thresholds as the primary UX;
- bounded sensor-window extraction from the existing common monotonic timeline;
- Room persistence for the active challenge/current reconnect evidence;
- one continuous CameraX recording through the entire challenge sequence;
- challenge timing/results added to final evidence metadata;
- explicit verification retry and upload retry paths without stale evidence reuse;
- admin challenge timeline and sensor-derived diagnostic view;
- web location search, map recentering and browser current-location selection;
- synthetic/API challenge tests and GitHub CI coverage;
- Phase 4 documentation.

## Acceptance status

**PHASE 4 ACCEPTED ON REAL HARDWARE — PASS.**

Observed real-device evidence includes successful uploaded challenge sessions with all final challenge results passing, real gyroscope/rotation-vector/accelerometer/location samples, Video / Motion sensors / Location / Manifest all received by the backend, and challenge history visible in the admin dashboard. A real retry flow was observed where an INCONCLUSIVE challenge was followed by a fresh retry challenge and then PASS. The full retry allowance was also manually checked through the fourth total attempt (initial attempt plus three reattempts).

The physical test also confirmed the Phase 4 UX improvements: users can follow an animated phone/directional guide instead of estimating exact degrees, the map can search for a location or use the browser's current location, and retry actions are available for challenge/verification/upload failure paths.

Device model, Android version and formal per-sensor sample-rate statistics were not recorded during this acceptance run and must not be invented. See `docs/testing.md` for the exact observed record and remaining non-blocking measurement gaps.

## Security boundary

Phase 4 validates requested **phone movement from sensors**. It does not yet prove that external camera-scene motion matches that movement. A user could theoretically rotate the phone while filming prerecorded content.

Therefore Phase 4 intentionally does not include:

- OpenCV optical flow;
- camera motion estimation;
- feature matching/homography;
- visual-inertial sensor fusion;
- screen/replay detection;
- overall SiteProof trust score;
- final verified/flagged authenticity verdict;
- anomaly-detection ML.

Those remain later phases, with visual motion consistency beginning in Phase 5.

## Next phase

**Phase 5 — Visual Motion Verification** may now begin from the accepted Phase 4 baseline. Phase 5 must correlate challenge-time camera motion with the already synchronized challenge/sensor timeline rather than weakening or replacing the Phase 4 sensor checks.

## Source of truth

1. `docs/project-spec.md`
2. `docs/challenge-engine.md`
3. `docs/live-capture.md`
4. `docs/session-lifecycle.md`
5. `docs/api.md`
6. `docs/testing.md`
7. current repository code and actual CI/device results
