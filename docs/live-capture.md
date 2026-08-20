# Live Capture — Phase 3 foundation with Phase 4 challenges

## Purpose

The Android client records one continuous live field session: rear-camera video, motion sensors and GPS all share a monotonic timeline. Phase 4 keeps that Phase 3 evidence pipeline and adds server-generated phone-movement challenges while capture remains active.

The challenge result answers only whether the requested **phone movement** was detected from sensors. It does not yet establish camera-scene authenticity.

## Permissions and privacy

Requested at verification time only:

- `CAMERA`
- `ACCESS_FINE_LOCATION`
- `ACCESS_COARSE_LOCATION`

No microphone permission is requested. CameraX records without audio. No gallery/document picker exists in the verification flow. `FLAG_SECURE` is applied while the verification screen is visible as a privacy/discouragement control, not as replay prevention.

## Readiness sequence

1. Inspector opens a `READY` inspection.
2. App explains camera/location/sensor use and requests runtime permissions.
3. `SensorManager` reports actual capabilities; missing sensors are not fabricated.
4. Fused Location Provider obtains a fresh location.
5. Haversine distance plus reported accuracy is checked against the inspection radius.
6. Backend creates a short-lived verification session.
7. CameraX binds the rear camera preview.
8. On start, video, sensor and location capture begin before Challenge #1 is requested.

## Common timeline

At capture start:

```text
T0 = SystemClock.elapsedRealtimeNanos()
```

Sensor records use Android `SensorEvent.timestamp`:

```text
relativeTimestampNs = sensorTimestampNs - T0
```

Location uses `Location.elapsedRealtimeNanos` relative to the same T0. Camera metadata stores its video-start offset from T0. Phase 4 challenge start/end windows also use this same T0.

This shared monotonic clock is important because device wall clock changes must not make a physical motion appear earlier/later. It also prepares Phase 5 to map each challenge onto matching video frames.

## Sensors

`SensorRecorder` targets about 50 Hz with a 20,000 microsecond sampling period. Actual timestamps are authoritative; exact hardware sample rate is not assumed.

Full-session records stream into:

```text
sensors.ndjson.gz
```

During Phase 4, a bounded in-memory buffer also retains accelerometer, gyroscope and rotation-vector records for the current short challenge window. Online challenge submission sends only this relevant slice; the full raw session remains in the final evidence package.

Accelerometer remains required for the live evidence pipeline. Gyroscope is required for authoritative Phase 4 rotate/tilt validation; insufficient gyroscope data produces `INCONCLUSIVE`. Rotation vector is used as an independent orientation cross-check when available.

## Challenge flow during capture

```text
continuous CameraX + sensors + GPS running
        ↓
server issues current challenge only
        ↓
Android starts server challenge with monotonic timestamp
        ↓
~500 ms still baseline
        ↓
inspector performs requested movement
        ↓
short settling period
        ↓
Android extracts sensor slice
        ↓
backend independently validates PASS / FAIL / INCONCLUSIVE
        ↓
next server challenge (if required)
```

The camera is never stopped/restarted between challenges.

The normal UI shows the challenge instruction, approximate target, server-aligned countdown and coarse feedback such as “Movement detected…” / “Checking challenge…”. It deliberately does not expose raw gyroscope values or secret validation tolerances.

## Server-aligned countdown

Challenge issuance includes `serverTime`, `issuedAt` and `expiresAt`. Android calculates the visible remaining interval from the server response and uses a local monotonic deadline for smooth countdown updates. The backend still makes the final expiry decision.

## Location during capture

High-accuracy updates continue at about 1 Hz. The session is short, so location samples may be held briefly in memory and written to `locations.json.gz` when capture stops. Listeners are removed on stop/abort.

## Camera

CameraX `Preview` + `VideoCapture<Recorder>` uses the rear camera. Quality selection prefers FHD with HD/SD fallbacks. Audio is disabled. Output is written to app-private storage:

```text
filesDir/verification/session_<uuid>/capture.mp4
```

Capture constraints remain:

- minimum accepted: 8 seconds;
- typical target: 15–30 seconds;
- maximum: 60 seconds.

Phase 4 automatically aborts if the challenge sequence cannot finish before the continuous-capture hard limit.

## Challenge interruption/network policy

If the app backgrounds/locks during live challenges, the security-focused first implementation aborts the verification session. A proof session is not silently resumed after a process interruption.

If network connectivity disappears **after a challenge has already been issued/started**, the sensor slice is preserved locally and the UI waits for reconnection. Android cannot fetch a future challenge while offline; there is no offline challenge batch.

After all challenges finish and capture is packaged, the existing WorkManager evidence-upload retry flow handles later connectivity loss.

## Evidence packaging

The Phase 3 evidence package remains:

```text
capture.mp4
sensors.ndjson.gz
locations.json.gz
metadata.json
manifest.json
```

`metadata.json` now also carries a compact challenge timeline containing challenge ID/type and relative issued/started/completed times plus result/score. This is metadata for later analysis, not a final trust verdict.

Individual challenge sensor slices may temporarily exist in app-private storage to support an online retry. They are not exposed through Gallery/Downloads and are not treated as the canonical full-session evidence stream.

## Coordinate system

The verification Activity is portrait-locked. Rotation left/right uses the portrait device Y angular-velocity axis; tilt up/down uses the X axis. Backend direction signs are typed configuration so physical-device testing can validate/tune them without embedding assumptions across the codebase. See `docs/challenge-engine.md` for the math and limitations.

## Phase boundary

Phase 4 confirms sensor-based phone movement only. It **cannot yet confirm that the camera scene moved consistently with that phone motion**. Continuous video + challenge timestamps + the sensor timeline are intentionally retained so Phase 5 can implement that visual-inertial comparison.
