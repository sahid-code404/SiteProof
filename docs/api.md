# SiteProof REST API — through Phase 4

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

Inspector-only. Requires the caller to own the active assignment and the inspection to be `READY`. Creates a short-lived verification session and returns `sessionId`, expiry, server time and clock-offset metadata.

### `GET /inspections/{inspectionId}/sessions/latest`

Returns the most recent organization/assignment-scoped verification session, used by Android/admin UI.

### `GET /sessions/{sessionId}`

Returns session lifecycle/evidence-presence information. This endpoint does not return raw challenge sensor data.

### `POST /sessions/{sessionId}/start-capture`

Inspector-only. Request includes fresh location, monotonic capture anchor and device sensor capabilities. The backend verifies radius/uncertainty and changes the session to `CAPTURING`.

### `POST /sessions/{sessionId}/capture-complete`

Inspector-only. Phase 4 accepts this only after the challenge sequence reaches `CHALLENGES_COMPLETED` or `CHALLENGE_FAILED`. The body contains capture/sensor/location summaries, not raw evidence.

### `POST /sessions/{sessionId}/abort`

Inspector-only. Terminates an active live proof session with a structured reason.

## Phase 4 challenge API

The client **cannot choose the challenge type**. There is no endpoint accepting `{ "type": "ROTATE_RIGHT" }` from Android.

### `POST /sessions/{sessionId}/challenges/next`

Issues only the current server-generated challenge.

Server checks:

- active assigned inspector owns the session;
- same organization;
- session is live and not expired;
- no non-expired active challenge already exists (if one does, the same one is returned idempotently);
- retry/required-count policy;
- future challenges are not returned.

Response:

```json
{
  "challengeId": "uuid",
  "sequenceNumber": 1,
  "attemptNumber": 1,
  "totalChallenges": 3,
  "type": "ROTATE_RIGHT",
  "instruction": "Rotate your phone to the right.",
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

Possible challenge types in Phase 4:

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

The backend verifies nonce, challenge/session ownership, expiry, current challenge state and that the monotonic start does not precede the capture anchor. A challenge cannot be started twice.

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

The backend independently checks:

- ownership/organization;
- challenge state;
- nonce and nonce consumption;
- idempotency/replay evidence hash;
- monotonic timestamp ordering;
- samples inside the declared window;
- challenge window aligned to the capture/start monotonic anchors;
- evidence physical time before/near challenge expiry;
- sensor quality and movement direction/magnitude/agreement.

Result:

```json
{
  "challengeId": "uuid",
  "sequenceNumber": 1,
  "type": "ROTATE_RIGHT",
  "result": "PASS",
  "score": 0.91,
  "reasons": [
    "Rotation direction matched the requested movement.",
    "Observed gyroscope angle was 40.8 degrees."
  ],
  "metrics": {
    "targetDegrees": 38.2,
    "observedGyroDegrees": 40.8,
    "observedRotationVectorDegrees": 39.6,
    "sensorDifferenceDegrees": 1.2,
    "movementDurationMs": 1410
  },
  "sensorQuality": {},
  "retryAllowed": false,
  "sequenceComplete": false,
  "sessionStatus": "CHALLENGES_IN_PROGRESS",
  "serverTime": "2026-...Z"
}
```

`result` is one of `PASS`, `FAIL`, `INCONCLUSIVE`. The `score` is a per-movement sensor score, not an overall authenticity/trust score.

Legitimate network retry with the same challenge, nonce, idempotency key and identical evidence returns the existing calculated result. A changed replay after terminal completion is rejected.

### `GET /sessions/{sessionId}/challenges`

Organization-scoped read endpoint for the admin/reviewer timeline and inspector-owned session. Returns attempts, result, score, explainable metrics, timestamps and sensor-quality summaries. It does not expose raw sensor samples.

## Challenge error codes

The challenge service uses structured codes including:

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

Depending on security context, cross-organization/non-owner resources may intentionally appear as 404 instead of revealing that another organization's challenge exists.

## Evidence upload

Phase 3 routes remain the canonical full-session upload transport:

```text
POST /sessions/{sessionId}/evidence/initiate
PUT  /evidence/{fileId}/content
POST /sessions/{sessionId}/evidence/complete
GET  /sessions/{sessionId}/evidence
GET  /evidence/{fileId}/content
```

The final package contains one continuous video plus full sensor/location evidence, metadata and manifest. Phase 4 adds a compact challenge timeline to session metadata. Per-file bytes are independently SHA-256 checked on the backend.

## Phase boundary

Challenge results confirm sensor-derived phone movement only. The API intentionally provides no overall `SiteProofScore`, `VERIFIED`, `AUTHENTIC`, replay verdict or camera/sensor consistency result in Phase 4.
