# Verification Session Lifecycle — through Phase 4

Inspection state and verification-session state are intentionally separate. Phase 4 inserts active challenge-response between capture start and capture completion.

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

`PROCESSING` still means evidence was received for later verification logic. It does not mean authentic/verified.

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
PROCESSING (reserved/later)     │
                                │
CHALLENGE_FAILED ───────────────┘
  ↓
CAPTURE_COMPLETED
```

Failure/termination states:

```text
ABORTED
EXPIRED
CHALLENGE_FAILED
UPLOAD_FAILED
```

`CHALLENGE_FAILED` means the configured Phase 4 explicit-failure limit was reached. It is **not** a final SiteProof authenticity verdict; capture can still be finalized and uploaded so later analysis/review has the complete evidence.

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

An inconclusive challenge may consume the configured single retry budget. A retry is a **new** challenge record and nonce for the same sequence number.

When all required sequence numbers have a terminal result, the session becomes `CHALLENGES_COMPLETED` unless the configured explicit-failure limit is reached, in which case it becomes `CHALLENGE_FAILED`.

## Capture completion

`POST /api/v1/sessions/{sessionId}/capture-complete` accepts only after `CHALLENGES_COMPLETED` or `CHALLENGE_FAILED`. It receives summaries, not raw evidence, and validates bounded duration, one video, required sensor counts and location samples.

Phase 4 deliberately rejects direct `CAPTURING → CAPTURE_COMPLETED` so the Android client cannot bypass server-generated liveness challenges.

## Upload

The Phase 3 evidence upload flow remains unchanged:

```text
CAPTURE_COMPLETED → UPLOADING → UPLOADED
                    │
                    └→ UPLOAD_FAILED → UPLOADING
```

The full evidence package still contains one continuous video and full sensor/location streams. Phase 4 adds challenge timing/result metadata to the session metadata so later visual analysis can locate the corresponding video intervals.

## Abort/background/process interruption

The Android live proof session is foreground-only. User cancellation, app backgrounding/locking or a capture failure aborts the session rather than silently resuming an old challenge. Active Room challenge metadata helps explain/recover a brief online-submission interruption, but it is not permission to resume an old process-killed liveness session.

## Phase boundary

No status in this document means identity or scene authenticity has been established. Phase 4 can say that a requested **phone movement** passed/failed/inconclusive from sensors. Camera-scene consistency, replay detection and the overall trust/final verdict remain later phases.
