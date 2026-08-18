# Phase 3 Session Lifecycle

Inspection state and verification-session state are intentionally separate.

## Inspection states used through Phase 3

```text
DRAFT → ASSIGNED → ACKNOWLEDGED → READY
                                  ↓
                           SESSION_STARTED
                                  ↓
                         EVIDENCE_UPLOADING
                                  ↓
                              PROCESSING
```

`CANCELLED` remains terminal for inspection management. `PROCESSING` in Phase 3 means evidence was received and is awaiting later verification logic; it does not mean verified.

## Verification session states

```text
CREATED → CAPTURING → CAPTURE_COMPLETED → UPLOADING → UPLOADED
   │          │              │                │
   ├──────────┴──────────────┴──────────────→ ABORTED
   └────────────────────────────────────────→ EXPIRED
                                      UPLOADING → UPLOAD_FAILED → UPLOADING
```

`PROCESSING` is reserved in the session enum for later server processing. The Phase 3 upload acceptance endpoint leaves the verification session at `UPLOADED` while the parent inspection is `PROCESSING`, matching the admin demonstration language “Session: UPLOADED / Awaiting verification analysis.”

## Creation authorization

`POST /api/v1/inspections/{inspectionId}/sessions` is inspector-only. The backend requires:

- same organization;
- active inspector profile;
- active assignment owned by that inspector;
- inspection state `READY`;
- deadline not passed;
- no conflicting active session.

A partial unique database index protects the one-active-session-per-inspection invariant in addition to service-layer locking/checks.

Session lifetime defaults to 15 minutes and is configurable. `device_session_id` is an idempotency key for creation, not a device identity.

## Capture start

`POST /api/v1/sessions/{sessionId}/start-capture` accepts a client wall clock, monotonic anchor, fresh location and capability metadata. The server records its own receipt time and validates the location against a frozen site/radius snapshot. Client time and capability flags remain untrusted metadata.

A session created before the deadline may start within the configurable grace period (default 120 seconds). After that it expires.

## Capture completion

`POST /api/v1/sessions/{sessionId}/capture-complete` receives summaries only, never raw evidence. It checks structural minimums such as duration, one video file, accelerometer samples, sensor samples for reported available sensors, and location samples.

## Upload

`POST /api/v1/sessions/{sessionId}/evidence/initiate` requires all Phase 3 evidence descriptors and an idempotency key. Retrying the same batch reuses logical evidence records/file IDs rather than creating duplicates.

Each file is uploaded through an authenticated `PUT` target. A failed hash/size moves the session to `UPLOAD_FAILED`; retry may re-upload the same logical record.

`POST /api/v1/sessions/{sessionId}/evidence/complete` requires all files to be uploaded and independently hash-verified and then structurally validates the package. Successful completion marks the session `UPLOADED` and inspection `PROCESSING`.

## Abort

`POST /api/v1/sessions/{sessionId}/abort` records a reason such as `USER_CANCELLED`, `CAMERA_ERROR`, `LOCATION_LOST`, `APP_INTERRUPTED`, `SENSOR_ERROR`, or `TIMEOUT`. An aborted session is not resumed; a new attempt requires a new session.

## Phase boundary

No transition in this document means authenticity has been established. `VERIFIED`, `FLAGGED`, approval/rejection, trust scoring and challenge validation are intentionally absent from Phase 3.
