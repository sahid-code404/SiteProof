# SiteProof REST API — through Phase 5

Base path: `/api/v1`

All authenticated endpoints use `Authorization: Bearer <access-token>`. FastAPI OpenAPI at `/docs` is the executable schema source.

## Error envelope

Business errors use a structured envelope:

```json
{
  "error": {
    "code": "CHALLENGE_EXPIRED",
    "message": "Challenge expired.",
    "details": {}
  }
}
```

Stack traces are not returned to API clients.

## Authentication

### `POST /auth/login`

Returns the access token and authenticated user.

### `GET /auth/me`

Returns the authenticated user resolved from the database.

## Inspectors and inspections

Phase 2 routes remain unchanged:

```text
GET  /inspectors
POST /inspectors
GET  /inspections
GET  /inspections/summary
POST /inspections
GET  /inspections/{inspectionId}
PATCH /inspections/{inspectionId}
POST /inspections/{inspectionId}/assign
POST /inspections/{inspectionId}/reassign
POST /inspections/{inspectionId}/acknowledge
POST /inspections/{inspectionId}/ready
POST /inspections/{inspectionId}/cancel
```

Administration is organization-scoped. Inspectors can access only their active assignments.

## Verification sessions

### `POST /inspections/{inspectionId}/sessions`

Inspector-only. Requires the caller to own the active assignment and the inspection to be `READY`. Creates a short-lived verification session and returns session/expiry/clock metadata.

### `GET /inspections/{inspectionId}/sessions/latest`

Returns the most recent organization/assignment-scoped verification session used by Android/admin UI.

### `GET /sessions/{sessionId}`

Returns session lifecycle and evidence-presence information. It does not return raw challenge sensor samples or raw computer-vision frames.

### `POST /sessions/{sessionId}/start-capture`

Inspector-only. Request includes fresh location, monotonic capture anchor and device sensor capabilities. The backend verifies radius/uncertainty and changes the session to `CAPTURING`.

### `POST /sessions/{sessionId}/capture-complete`

Inspector-only. Phase 4 accepts this only after the challenge sequence reaches `CHALLENGES_COMPLETED` or `CHALLENGE_FAILED`. The body contains capture/sensor/location summaries, not raw evidence.

### `POST /sessions/{sessionId}/abort`

Inspector-only. Terminates an active live proof session with a structured reason.

## Phase 4 challenge API

The client **cannot choose the challenge type**. Android never submits a trusted requested movement type or a trusted PASS/FAIL result.

### `POST /sessions/{sessionId}/challenges/next`

Issues only the current server-generated challenge. Repeating the request while one non-expired challenge is active returns the same challenge rather than generating or exposing a future challenge.

Response example:

```json
{
  "challengeId": "uuid",
  "sequenceNumber": 1,
  "attemptNumber": 1,
  "totalChallenges": 3,
  "type": "ROTATE_RIGHT",
  "instruction": "Rotate your phone slowly to the right. Keep the site visible and move smoothly.",
  "parameters": {
    "targetDegrees": 38.2,
    "minDegrees": 27.1,
    "maxDegrees": 51.4
  },
  "issuedAt": "2026-...Z",
  "expiresAt": "2026-...Z",
  "serverTime": "2026-...Z",
  "nonce": "high-entropy-random-value"
}
```

Supported movement types:

```text
ROTATE_LEFT
ROTATE_RIGHT
TILT_UP
TILT_DOWN
```

### `POST /challenges/{challengeId}/start`

Inspector-only. Starts exactly one issued challenge.

```json
{
  "nonce": "...",
  "clientMonotonicNs": 1234567890
}
```

The backend verifies nonce, challenge/session ownership, expiry, current state and monotonic start ordering.

### `POST /challenges/{challengeId}/submit`

Inspector-only. Sends the relevant raw sensor slice; the client does **not** send a trusted `PASS`/`FAIL` field.

```json
{
  "nonce": "...",
  "idempotencyKey": "...",
  "sensorWindow": {
    "startRelativeNs": 3400000000,
    "endRelativeNs": 6100000000
  },
  "samples": [
    {
      "type": "GYROSCOPE",
      "relativeTimestampNs": 3420000000,
      "values": [0.01, -0.62, 0.02],
      "accuracy": 3
    }
  ],
  "sensorSummary": {
    "gyroSamples": 135,
    "rotationVectorSamples": 132,
    "accelerometerSamples": 136
  }
}
```

The backend independently checks ownership, organization, state, nonce/consumption, replay/idempotency evidence hash, monotonic ordering, sample bounds, capture/challenge alignment, expiry, sensor quality and movement direction/magnitude/agreement.

Result example:

```json
{
  "challengeId": "uuid",
  "sequenceNumber": 1,
  "type": "ROTATE_RIGHT",
  "result": "PASS",
  "score": 0.91,
  "reasons": [
    "Rotation direction matched the requested movement."
  ],
  "metrics": {
    "targetDegrees": 38.2,
    "observedGyroDegrees": 40.8,
    "observedRotationVectorDegrees": 39.6,
    "movementDurationMs": 1410
  },
  "sensorQuality": {},
  "retryAllowed": false,
  "sequenceComplete": false,
  "sessionStatus": "CHALLENGES_IN_PROGRESS",
  "serverTime": "2026-...Z"
}
```

`result` is `PASS`, `FAIL` or `INCONCLUSIVE`. This is a per-movement **sensor result**, not an overall SiteProof authenticity score.

### `GET /sessions/{sessionId}/challenges`

Organization-scoped read endpoint for the admin/reviewer timeline and inspector-owned session. Returns attempts, result, score, explainable metrics, timestamps and sensor-quality summaries. It does not expose raw sensor samples.

## Challenge error codes

Challenge service codes include:

```text
CHALLENGE_NOT_FOUND
CHALLENGE_EXPIRED
CHALLENGE_ALREADY_COMPLETED
CHALLENGE_NONCE_INVALID
CHALLENGE_NOT_ACTIVE
CHALLENGE_NOT_SUPPORTED
SESSION_NOT_ACTIVE
SENSOR_EVIDENCE_INVALID
CHALLENGE_LIMIT_REACHED
CHALLENGES_REQUIRED
```

Cross-organization/non-owner resources may intentionally appear as 404 to avoid disclosing another organization's data.

## Evidence upload

The Phase 3 full-session upload remains canonical:

```text
POST /sessions/{sessionId}/evidence/initiate
PUT  /sessions/{sessionId}/evidence/{fileId}/content
POST /sessions/{sessionId}/evidence/complete
GET  /sessions/{sessionId}/evidence
GET  /sessions/{sessionId}/evidence/{fileId}/content
```

The final package contains one continuous video plus full sensor/location evidence, metadata and manifest. Phase 4 adds compact challenge timing/results to session metadata. Per-file bytes and the manifest are independently SHA-256 checked by the backend.

After a successful `evidence/complete`, Phase 5 queues visual analysis as a FastAPI background task. `PROCESSING` is a transient session state; the durable evidence session returns to `UPLOADED`, while `visual_motion_results` carries the independent visual processing/result state.

A repeated evidence-completion request with the same manifest hash remains idempotent even if visual analysis has already entered the transient `PROCESSING` state.

## Phase 5 visual-analysis API

Phase 5 APIs expose **camera-side visual evidence only**. They do not compare it with Phase 4 sensor results.

### `GET /sessions/{sessionId}/visual-analysis`

Roles: `ADMIN` or `REVIEWER`.

Organization scope is enforced. The endpoint returns the current configured analysis version and per-challenge camera-side measurements.

Example:

```json
{
  "sessionId": "uuid",
  "status": "SUCCESS",
  "analysisVersion": "vision-v1.0",
  "challenges": [
    {
      "challengeId": "uuid",
      "challengeType": "ROTATE_RIGHT",
      "analysisVersion": "vision-v1.0",
      "status": "SUCCESS",
      "visualDirection": "RIGHT",
      "estimatedRotationDegrees": 36.7,
      "translationX": -241.4,
      "translationY": 5.2,
      "scaleChange": 0.003,
      "motionStartMs": 4420,
      "motionEndMs": 5730,
      "featureCount": 355,
      "trackedFeatureCount": 302,
      "inlierRatio": 0.84,
      "confidence": 0.87,
      "sceneContinuityScore": 0.95,
      "duplicateFrameRatio": 0.01,
      "freezeDurationMs": 0,
      "invalidFrameRatio": 0.0,
      "visualQuality": "GOOD",
      "reasons": [
        "Visual motion was estimated from a dominant RANSAC-supported scene transform."
      ],
      "diagnostics": {}
    }
  ]
}
```

The numeric values above illustrate the schema only; they are not claimed project measurements.

### Visual-analysis statuses

```text
PENDING
PROCESSING
SUCCESS
INCONCLUSIVE
FAILED
```

Semantics:

- `SUCCESS`: the camera-side movement could be estimated with sufficient support;
- `INCONCLUSIVE`: valid media did not contain enough reliable visual evidence;
- `FAILED`: technical/structural processing failure;
- `PROCESSING`: background analysis currently active;
- `PENDING`: no current result rows yet.

`SUCCESS` does **not** mean the challenge or submission is authentic.

### Visual directions

```text
LEFT
RIGHT
UP
DOWN
MIXED
NONE
```

Direction is normalized to **physical camera movement semantics**, not raw image-content optical-flow direction. For example, a rightward camera yaw normally makes a static scene move left in image coordinates.

### Diagnostics

Authorized reviewer diagnostics may include:

- decoded codec/width/height/FPS/duration/frame count;
- challenge/video timeline window;
- sampled frame count;
- RANSAC-supported frame-pair count;
- feature coverage;
- foreground/outlier ratio;
- motion-energy curve;
- per-pair affine estimates;
- scene-cut/black-frame metrics;
- whether translation or labelled affine-rotation fallback supplied direction.

Raw video frames and raw optical-flow arrays are not returned by this endpoint.

### `POST /sessions/{sessionId}/visual-analysis/retry`

Roles: `ADMIN` or `REVIEWER`.

Returns `202 Accepted` and schedules a forced re-analysis of the current configured algorithm version. The unique `(challenge_id, analysis_version)` key prevents duplicate conflicting rows for the same version.

A structurally corrupt video should not be retried forever. The visual result diagnostics distinguish retryable/temporary failures from permanent malformed-media failures.

## Phase 5 audit events

```text
VISUAL_ANALYSIS_STARTED
VISUAL_ANALYSIS_COMPLETED
VISUAL_ANALYSIS_INCONCLUSIVE
VISUAL_ANALYSIS_FAILED
```

The audit log stores event metadata, not raw video frames or raw optical-flow tracks.

## Phase boundary

Through Phase 5, SiteProof has two **independent** evidence families:

```text
Phase 4: sensor-derived phone movement
Phase 5: visual-derived camera/scene movement
```

The API intentionally provides no sensor-camera consistency percentage, final replay-risk classification, overall SiteProof trust score, `VERIFIED`, `FLAGGED` or `AUTHENTIC` verdict.

That comparison belongs to Phase 6.
