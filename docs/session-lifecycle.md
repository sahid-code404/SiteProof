# Verification Session Lifecycle — through Phase 5

Inspection state and verification-session state are intentionally separate. Phase 4 inserts active challenge-response between capture start and capture completion. Phase 5 adds a transient background visual-processing stage after evidence upload.

## Inspection states

```text
DRAFT → ASSIGNED → ACKNOWLEDGED → READY
                                  ↓
                           SESSION_STARTED
                                  ↓
                         EVIDENCE_UPLOADING
                                  ↓
                              PROCESSING
```

Inspection `PROCESSING` means evidence has been received for verification logic. It does not mean authentic or verified.

## Verification session states

```text
CREATED
  ↓
CAPTURING
  ↓
CHALLENGES_IN_PROGRESS
  ↓
CHALLENGES_COMPLETED ───────────┐
  ↓                             │
CAPTURE_COMPLETED               │
  ↓                             │
UPLOADING → UPLOAD_FAILED ──────┤
  ↓                             │
UPLOADED                        │
  ↓                             │
PROCESSING                      │  Phase 5 visual analysis is running
  ↓                             │
UPLOADED                        │  evidence remains durably uploaded
                                │
CHALLENGE_FAILED ───────────────┘
  ↓
CAPTURE_COMPLETED
```

Failure/termination states used by capture/upload remain:

```text
ABORTED
EXPIRED
CHALLENGE_FAILED
UPLOAD_FAILED
```

`CHALLENGE_FAILED` means the configured Phase 4 explicit-failure limit was reached. It is **not** a final SiteProof authenticity verdict; capture can still be finalized and uploaded.

Phase 5 visual processing does not add a new terminal verification-session verdict. Per-challenge `visual_motion_results` carry their own analysis state:

```text
PENDING
PROCESSING
SUCCESS
INCONCLUSIVE
FAILED
```

## Creation authorization

`POST /api/v1/inspections/{inspectionId}/sessions` is inspector-only. The backend requires the same organization, an active inspector profile, active assignment owned by that inspector, inspection `READY`, valid deadline and no conflicting active session.

The database partial unique index treats Phase 4 challenge states as active so a second verification session cannot be opened while one challenge sequence is underway.

## Capture start

`POST /api/v1/sessions/{sessionId}/start-capture` records the authoritative server receipt time plus the client's monotonic capture anchor, fresh location and capabilities. If accepted:

```text
session:    CREATED → CAPTURING
inspection: READY → SESSION_STARTED
```

The camera, sensors and GPS then remain active continuously.

## Challenge stage

The first call to:

```text
POST /api/v1/sessions/{sessionId}/challenges/next
```

changes the session to `CHALLENGES_IN_PROGRESS`. Only the current challenge is returned. The backend will not reveal future challenge types/angles.

Each challenge follows:

```text
ISSUED → STARTED → PASSED | FAILED | INCONCLUSIVE
  │          │
  └──────────┴────→ EXPIRED
```

An inconclusive challenge may consume the configured retry budget. A retry is a **new** challenge record and nonce for the same sequence number.

When all required sequence numbers have a terminal result, the session becomes `CHALLENGES_COMPLETED` unless the explicit-failure limit is reached, in which case it becomes `CHALLENGE_FAILED`.

## Capture completion

`POST /api/v1/sessions/{sessionId}/capture-complete` accepts only after `CHALLENGES_COMPLETED` or `CHALLENGE_FAILED`. It receives summaries, not raw evidence, and validates bounded duration, one video, required sensor counts and location samples.

Direct `CAPTURING → CAPTURE_COMPLETED` remains rejected so Android cannot bypass server-generated liveness challenges.

## Upload

The Phase 3 upload transport remains canonical:

```text
CAPTURE_COMPLETED → UPLOADING → UPLOADED
                    │
                    └→ UPLOAD_FAILED → UPLOADING
```

The full package contains one continuous video plus complete sensor/location streams, metadata and manifest. Challenge relative timestamps in metadata share the same capture anchor as `videoStartRelativeNs`, which lets Phase 5 locate the correct video windows.

Evidence-completion retry remains idempotent. If a delayed Android completion receipt arrives while the background worker has already moved the session temporarily to `PROCESSING`, the same manifest hash is still accepted as the already-completed upload.

## Phase 5 visual processing

After verified upload:

```text
UPLOADED
   ↓
PROCESSING
   ↓
OpenCV video metadata + timeline validation
   ↓
per-challenge visual analysis
   ↓
visual_motion_results stored
   ↓
UPLOADED
```

`PROCESSING` is transient and does not replace the durable fact that evidence was successfully uploaded. A successful, inconclusive or failed visual result lives in the versioned `visual_motion_results` row for each challenge.

If a later challenge window fails to process, already terminal `SUCCESS`/`INCONCLUSIVE` visual results from earlier challenges are preserved rather than overwritten.

Temporary storage/processing failures can be retried by an authorized reviewer. Structurally invalid media is recorded as failed without leaving the session stuck in `PROCESSING`.

## Abort/background/process interruption

The Android live proof session remains foreground-only. User cancellation, app backgrounding/locking or capture failure aborts the session rather than silently resuming an old challenge. Phase 5 does not change this live-capture policy.

## Phase boundary

No status in this document means identity or scene authenticity has been established.

Through Phase 5 SiteProof has independent evidence:

```text
Phase 4: requested phone movement from sensors
Phase 5: camera/scene visual movement from video
```

Camera-sensor consistency, contradiction detection, replay classification and the overall trust/final verdict remain Phase 6 and later.
