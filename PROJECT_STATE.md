# Project State

Current development branch: **Phase 3 — Live Capture, Location & Multi-Sensor Evidence Collection**

Phase 3 is stacked on the tested Phase 2 branch. Phase 2 automated CI is green, but its physical-device acceptance remains a separate prerequisite before either milestone should be called fully accepted.

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

Not yet accepted until a real Android device successfully sends an actual CameraX video plus real sensor/location packages and manifest to the backend. Never fill in or claim real-device results without performing that test.

## Phase boundary

Phase 3 does **not** implement randomized movement challenges, OpenCV optical flow, visual-inertial verification, replay detection, trust scoring, authenticity verdicts or AI anomaly detection.

Source of truth:

1. `docs/project-spec.md`
2. `docs/live-capture.md`
3. `docs/evidence-format.md`
4. `docs/session-lifecycle.md`
5. current repository code and passing tests
