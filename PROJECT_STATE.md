# Project State

Current development branch: **Phase 3 — Live Capture, Location & Multi-Sensor Evidence Collection**

Phase 2 prerequisite: **PASS — physical-device acceptance completed on 2026-08-19.** The Phase 2 seed/login fixes and Android account-switch isolation fix have been carried forward into this Phase 3 branch before Phase 3 hardware testing.

## Phase 3 implementation status

Implemented in code:

- verification-session state machine and persistence;
- evidence-file metadata and object-storage abstraction;
- authenticated, idempotent upload pipeline with independent SHA-256 verification;
- Android runtime permission flow for camera and fine location;
- CameraX rear-camera preview and video capture without microphone/audio;
- accelerometer, gyroscope, rotation-vector and optional magnetometer capture;
- Fused Location Provider freshness, accuracy and radius checks;
- common monotonic capture timeline;
- app-private evidence packaging and manifest generation;
- Room pending-upload tracking;
- WorkManager network-constrained retry;
- admin evidence/session status and authenticated video preview;
- automated backend/web/Android checks in GitHub CI.

## Current acceptance gate

**Phase 3 real-device acceptance — NOT TESTED YET on the updated branch.**

Phase 3 is not complete until a physical Android phone successfully creates one actual CameraX recording plus real sensor/location packages and manifest from the same live session, survives the required temporary-offline retention/retry test, uploads the evidence to the backend, and shows the received evidence in the admin dashboard.

Do not fabricate device model, Android version, sensor availability, sample behavior, upload behavior or timing results. Record only observed values from the physical run.

## Carry-forward fixes from accepted Phase 2

- demo seed addresses use/migrate to `@siteproof.example.com` so the real login schema accepts them;
- legacy demo identities are migrated in place without duplicate inspector employee-code collisions;
- Android authenticated navigation/ViewModel state is session-scoped so an Inspector One → logout → Inspector Two switch cannot retain Inspector One's in-memory inspection list;
- regression coverage for those fixes is carried forward.

## Phase boundary

Phase 3 does **not** implement randomized movement challenges, OpenCV optical flow, visual-inertial verification, replay detection, trust scoring, authenticity verdicts or AI anomaly detection.

Source of truth:

1. `docs/project-spec.md`
2. `docs/live-capture.md`
3. `docs/evidence-format.md`
4. `docs/session-lifecycle.md`
5. `docs/testing.md`
6. current repository code and passing tests

Next task: run the exact real-device Phase 3 acceptance flow in `docs/testing.md` after the updated branch passes CI.
