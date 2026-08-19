# Phase 4 Active Challenge-Response Engine

## Purpose and phase boundary

Phase 4 adds an active phone-movement proof to the continuous evidence capture built in Phase 3. During one live CameraX recording, the backend reveals exactly one short-lived movement challenge at a time. Android records a sensor window from the same monotonic timeline and sends that slice to the backend. The backend, not the Android client, calculates `PASS`, `FAIL`, or `INCONCLUSIVE`.

Phase 4 answers a limited question:

> Did the phone physically perform the requested movement during this live verification session?

It does **not** yet prove that the visible camera scene moved consistently with the phone. Optical flow, camera-motion estimation, homography, visual-inertial fusion and replay/screen analysis are Phase 5 work. Therefore a person could still physically move the phone while pointing it at a prerecorded display. No final SiteProof authenticity/trust score is produced in Phase 4.

## Challenge types

The first supported types are deliberately small and safe:

- `ROTATE_RIGHT`
- `ROTATE_LEFT`
- `TILT_UP`
- `TILT_DOWN`

`MOVE_FORWARD` is not enabled yet because reliable short-distance translation detection is more device-dependent. The four rotational challenges are sufficient to establish the Phase 4 server/challenge/sensor architecture before adding harder movement classes.

## Server-side generation

`ChallengeGenerator` runs only on the backend. Android cannot choose a challenge type or request a target angle. For each issued challenge the server:

1. chooses the current challenge type from all supported Phase 4 types;
2. filters the exact previous type to avoid monotonous immediate repetition;
3. chooses a comfortable target angle inside the configured range;
4. creates an acceptable lower/upper range around the target;
5. generates a cryptographically random nonce with `secrets.token_urlsafe`;
6. stores the challenge and expiry;
7. returns only that challenge.

The MVP sequence is configurable and defaults to three challenges. The sequence number does **not** determine whether the next movement will be a rotation or tilt: challenge type, direction and target are selected on the server at issuance. The next challenge is not generated/revealed to Android until the current one has a terminal result.

Default target ranges:

```text
rotation: 25°–55°
tilt:     22°–45°
```

The backend never requests extreme body motion, running, backward walking, stair climbing or other unsafe instructions.

## Challenge lifecycle

```text
ISSUED
  ↓
STARTED
  ↓
PASSED | FAILED | INCONCLUSIVE

ISSUED/STARTED → EXPIRED
```

An inconclusive result may receive one replacement challenge when the configured retry budget is available. The replacement gets a new database ID, newly randomized parameters and a new nonce. A clear failure does not immediately abort the session; the remaining challenges continue so the later trust engine can decide how much that failure should matter.

The verification session lifecycle around challenges is:

```text
CREATED
  ↓
CAPTURING
  ↓
CHALLENGES_IN_PROGRESS
  ↓
CHALLENGES_COMPLETED
  ↓
CAPTURE_COMPLETED → UPLOADING → UPLOADED
```

If the configured number of explicit challenge failures is reached, the challenge stage becomes `CHALLENGE_FAILED`. That is a challenge-stage outcome, **not** a final authenticity verdict. The continuous capture may still be completed and uploaded for later review/Phase 5 processing.

## APIs

All challenge-performance endpoints require the active assigned inspector. Admin/reviewer access is read-only through the challenge timeline endpoint.

```text
POST /api/v1/sessions/{sessionId}/challenges/next
POST /api/v1/challenges/{challengeId}/start
POST /api/v1/challenges/{challengeId}/submit
GET  /api/v1/sessions/{sessionId}/challenges
```

`/challenges/next` is idempotent while one non-expired challenge is active. Repeating it returns the same current challenge rather than creating or leaking the future sequence.

### Issued payload

A typical response contains:

```json
{
  "challengeId": "uuid",
  "sequenceNumber": 1,
  "attemptNumber": 1,
  "totalChallenges": 3,
  "type": "ROTATE_RIGHT",
  "instruction": "Rotate your phone to the right.",
  "parameters": {
    "targetDegrees": 38.0,
    "minDegrees": 27.5,
    "maxDegrees": 51.0
  },
  "issuedAt": "...",
  "expiresAt": "...",
  "serverTime": "...",
  "nonce": "..."
}
```

Android derives its displayed countdown from `serverTime → expiresAt`; it does not rely on the wall clock of the phone alone.

## Sensor evidence window

The whole session still writes raw sensor records to `sensors.ndjson.gz`. For online challenge validation, `SensorRecorder` additionally retains a bounded in-memory copy of accelerometer, gyroscope and rotation-vector records. Only the current challenge interval is extracted and sent to the challenge endpoint.

A challenge starts with a short still baseline, followed by movement and settling:

```text
server challenge displayed
        ↓
~500 ms baseline
        ↓
movement onset
        ↓
requested movement
        ↓
~350 ms settling support
        ↓
sensor slice submitted
```

Each sample includes a timestamp relative to the Phase 3 capture anchor:

```text
relativeTimestampNs = SensorEvent.timestamp - captureT0
```

The same `captureT0 = SystemClock.elapsedRealtimeNanos()` anchors the full sensor package, location timeline and challenge windows. This lets Phase 5 locate the corresponding video interval later.

The online slice includes raw samples rather than a client-calculated pass/fail result. Client-side movement detection is used only to make the UI responsive.

## Android coordinate assumptions

The verification Activity is portrait-locked to keep challenge semantics stable for the first implementation. Android sensor axes follow the device coordinate system:

- +X: toward the device's right edge;
- +Y: toward the device's top edge;
- +Z: out of the screen.

For the current portrait implementation:

- rotate left/right uses the gyroscope Y component;
- tilt up/down uses the gyroscope X component;
- the corresponding component of the relative rotation-vector quaternion is used as an independent cross-check.

Direction signs are typed backend configuration (`ROTATION_RIGHT_SIGN`, `TILT_DOWN_SIGN`) rather than buried constants. Physical-device trials must verify/tune these signs before Phase 4 is accepted on real hardware.

This implementation intentionally does not claim universal landscape/orientation remapping yet because the inspector capture screen is locked to portrait.

## Gyroscope mathematics

A gyroscope reports angular velocity in radians per second:

```text
ω(t) [rad/s]
```

Angular displacement is the time integral:

```text
θ = ∫ ω(t) dt
```

For discrete sensor samples, SiteProof uses the trapezoidal approximation:

```text
θ ≈ Σ ((ωᵢ + ωᵢ₊₁) / 2) Δtᵢ
```

The result is converted from radians to degrees.

A short baseline estimates gyroscope bias before movement. This matters because a real gyroscope can report a small non-zero angular velocity even when motionless. Integrating that offset over time produces drift. Subtracting the local baseline reduces, but does not eliminate, this error.

Movement onset is detected when corrected angular velocity rises above a configured threshold. Settling is supported by looking for low angular velocity for a short interval. Actual timestamps are used; the validator never assumes an exact 50 Hz rate.

## Rotation-vector cross-check

Android's rotation-vector sensor provides an orientation quaternion. For a challenge window, the validator forms the relative orientation:

```text
q_relative = inverse(q_initial) × q_final
```

It converts that relative quaternion to axis-angle form and reads the challenge-axis component in degrees. This gives an orientation change estimate independent from directly integrating the gyroscope.

Example:

```text
requested:           rotate right ≈ 40°
gyroscope integral:  41.8°
rotation vector:     39.9°
difference:           1.9°
```

Agreement supports the result. A large contradiction is returned as `INCONCLUSIVE` rather than pretending one sensor is certainly correct.

## Score

The sensor-only movement score is continuous and explainable. Default normalized weights are:

```text
direction          0.30
angle magnitude    0.30
sensor agreement   0.20
timing             0.10
smoothness         0.10
```

The score is not a SiteProof trust score. It belongs only to one requested movement.

Default interpretation:

```text
score >= 0.75       candidate PASS
0.50–0.74           candidate INCONCLUSIVE
score < 0.50        candidate FAIL
```

Safety rules override the weighted score where appropriate:

- strong movement in the wrong requested direction → `FAIL`;
- strong gyroscope/rotation-vector contradiction → `INCONCLUSIVE`;
- clearly too-small movement → `FAIL`;
- missing/too-sparse gyroscope evidence → `INCONCLUSIVE`.

This prevents clean timing/agreement components from accidentally turning a tiny movement into a pass.

## Explainable metrics

The backend stores result diagnostics for admin/debug use, for example:

```text
targetDegrees
minDegrees
maxDegrees
observedGyroDegrees
observedRotationVectorDegrees
sensorDifferenceDegrees
movementDurationMs
gyroBiasRadPerSecond
movementSamples
directionScore
angleScore
sensorAgreement
timingScore
smoothnessScore
```

Sensor quality also records sample count, average interval, maximum gap and reported accuracy distribution. Raw challenge sensor samples are **not** written to the audit log.

## Nonce, expiry and replay protection

Every challenge has a high-entropy random nonce that is independent from user ID, session ID and timestamps. The server requires that nonce at start and submit.

Submission protection combines:

```text
challenge ID
+ nonce
+ per-challenge idempotency key
+ SHA-256 of the submitted sensor evidence document
```

A legitimate network retry with the same idempotency key and identical evidence receives the already-calculated result. A changed replay after the challenge is terminal is rejected.

Challenge expiry defaults to 15 seconds. The server checks both server-side expiry and whether the client monotonic sensor window aligns with the capture/challenge anchors. Network transfer latency is therefore not treated as physical movement duration.

## Network interruption

Future challenges are never downloaded in a batch. If connectivity disappears after the current challenge starts, Android can finish the local sensor slice and stores its current active-challenge metadata/evidence in app-private storage/Room. It then waits for network before authoritative submission and before requesting a future challenge.

Transport failures are distinguished from server challenge rejections. A genuine network failure enters the reconnect state with the current evidence preserved. A server-side rejection such as an invalid/stale challenge does not get mislabeled as “offline”; the security-focused client aborts that live proof rather than reusing stale evidence.

The process-kill/background policy is intentionally stricter: a live proof session should remain foregrounded. Backgrounding/locking during an active challenge aborts the session rather than silently continuing capture.

## Continuous camera and Phase 5 readiness

CameraX starts once before the first challenge and remains active through all challenges. It is not restarted per challenge. Final metadata includes relative challenge issued/started/completed timestamps alongside the same capture timeline.

That gives Phase 5 the three inputs it needs:

```text
continuous video
+ challenge timing windows
+ synchronized sensor timeline
```

Phase 5 can then compare sensor-inferred movement with visual camera motion. Phase 4 deliberately stops before doing that comparison.

## Configuration

The main environment options are documented in `.env.example` and include:

```text
CHALLENGE_COUNT
CHALLENGE_TIMEOUT_SECONDS
CHALLENGE_BASELINE_MS
CHALLENGE_SETTLING_MS
CHALLENGE_PASS_THRESHOLD
CHALLENGE_INCONCLUSIVE_THRESHOLD
CHALLENGE_MAX_RETRIES
CHALLENGE_FAILURE_LIMIT
ROTATION_MIN_TARGET_DEGREES
ROTATION_MAX_TARGET_DEGREES
TILT_MIN_TARGET_DEGREES
TILT_MAX_TARGET_DEGREES
ROTATION_RIGHT_SIGN
TILT_DOWN_SIGN
```

Thresholds must be tuned from genuine device measurements. Do not tune them by inventing desired results.

## Known limitations

- sensor-only movement cannot yet prove the external scene is live;
- sensor axes/signs must be confirmed on real devices even though the UI is portrait-locked;
- threshold values are prototype defaults until false-rejection/false-acceptance trials are performed;
- rotation-vector quality/implementation varies by device;
- no offline future-challenge batch is supported;
- `MOVE_FORWARD` is intentionally deferred;
- no overall authenticity verdict exists in Phase 4.
