# SiteProof — Full-Stack Multi-Sensor Proof-of-Physical-Presence Platform

You are a senior software architect, Android engineer, backend engineer, computer-vision engineer, security engineer, DevOps engineer, and QA engineer working together.

Your task is to design and implement a production-quality final-year B.Tech project called **SiteProof**.

Do not generate a toy application, static prototype, fake dashboard, or UI-only demo. Build a functioning end-to-end system incrementally, with clean architecture, documentation, tests, and reproducible local deployment.

---

# 1. PROJECT NAME

**SiteProof**

Full title:

**SiteProof — Active Multi-Sensor Proof-of-Physical-Presence and Tamper-Resistant Field Verification System**

---

# 2. CORE PROBLEM

Organizations frequently depend on photographs and videos submitted by field workers, inspectors, contractors, surveyors, insurance agents, infrastructure teams, NGOs, and other remote personnel.

Traditional photographic evidence is weak because it may be:

- captured earlier and reused;
- captured at another location;
- downloaded from the internet;
- displayed on another screen and photographed;
- replayed from a prerecorded video;
- edited before submission;
- submitted with manipulated metadata;
- captured while GPS information is spoofed;
- generated or altered artificially;
- submitted by someone who never physically visited the claimed site.

GPS coordinates and timestamps alone should therefore not be treated as sufficient proof.

SiteProof should provide stronger evidence that:

> **A legitimate mobile device physically observed a particular scene, at approximately the claimed place and time, during an unpredictable live verification session.**

SiteProof must accomplish this by combining multiple independent signals rather than trusting any one signal.

---

# 3. IMPORTANT SECURITY PRINCIPLE

SiteProof must NOT claim that it provides mathematically perfect or legally absolute proof.

The system provides a:

**multi-signal authenticity / confidence score**

based on independent evidence.

The system should explicitly distinguish between:

- verified signals;
- partially verified signals;
- unavailable signals;
- suspicious signals;
- conflicting signals.

Never represent GPS, AI, computer vision, or device attestation as infallible.

---

# 4. PRIMARY USE CASE

For the first complete implementation, optimize SiteProof for:

## Infrastructure Field Inspection

Example:

A road-maintenance authority receives a complaint that a pothole has been repaired.

An administrator creates an inspection assignment:

```
Inspection:
Verify repaired pothole

Location:
22.5726, 88.3639

Allowed radius:
100 metres

Deadline:
18 August 2026, 18:00

Assigned inspector:
Inspector A

```

The inspector travels to the site.

Instead of uploading an ordinary photograph, they must complete an unpredictable live SiteProof verification session.

---

# 5. SYSTEM ARCHITECTURE

Build three major applications:

```
                SITEPROOF PLATFORM

       ┌────────────────────────────┐
       │      Android Capture       │
       │           App              │
       │                            │
       │ Camera                     │
       │ GPS                        │
       │ Accelerometer              │
       │ Gyroscope                  │
       │ Magnetometer               │
       │ Rotation Vector            │
       │ Device Attestation         │
       │ Wi-Fi Environment          │
       │ Challenge Execution        │
       └──────────────┬─────────────┘
                      │
                    HTTPS
                      │
                      ▼
       ┌────────────────────────────┐
       │        Backend API         │
       │                            │
       │ Authentication             │
       │ Inspection Management      │
       │ Evidence Upload            │
       │ Challenge Generation       │
       │ Verification Engine        │
       │ Cryptographic Hashing      │
       │ Report Generation          │
       │ Audit Logging              │
       └──────────────┬─────────────┘
                      │
                      ▼
       ┌────────────────────────────┐
       │       Web Dashboard        │
       │                            │
       │ Inspection creation        │
       │ Assignment                 │
       │ Verification reports       │
       │ Evidence viewer            │
       │ Map                        │
       │ Risk indicators            │
       │ Audit logs                 │
       └────────────────────────────┘

```

---

# 6. RECOMMENDED TECHNOLOGY STACK

## Android

Use:

- Kotlin
- Jetpack Compose
- CameraX
- Android SensorManager
- FusedLocationProviderClient
- Room for temporary/offline local storage
- WorkManager for reliable uploads
- Retrofit or Ktor client
- Kotlin Coroutines
- DataStore
- Android Keystore
- Play Integrity API when practical

Do not unnecessarily depend on Firebase for core business logic.

---

## Backend

Use:

- Python
- FastAPI
- SQLAlchemy 2
- Alembic
- Pydantic
- PostgreSQL
- Redis where beneficial
- Celery/RQ/background workers only if required
- OpenCV
- NumPy
- SciPy
- cryptography library
- JWT-based authentication
- object storage abstraction for evidence files

During local development, MinIO may be used for evidence storage.

Production storage should support an S3-compatible provider.

---

## Web dashboard

Use:

- React
- TypeScript
- Vite or Next.js
- Tailwind CSS
- TanStack Query
- React Hook Form
- Zod
- map visualization using OpenStreetMap/Leaflet if appropriate

Keep frontend architecture clean.

---

## DevOps

Use:

- Docker
- Docker Compose
- GitHub Actions
- `.env.example`
- health-check endpoints
- structured logging
- automated backend tests
- frontend linting
- Android tests where practical

---

# 7. USER ROLES

Implement the following roles.

## Administrator

Can:

- create organizations;
- manage inspectors;
- create inspection assignments;
- assign inspectors;
- specify expected location;
- specify allowed geofence radius;
- specify deadline;
- review verification reports;
- approve/reject submissions;
- inspect evidence;
- view audit logs.

## Inspector

Can:

- authenticate in Android application;
- view assigned inspections;
- navigate to inspection site;
- begin SiteProof session;
- perform generated challenges;
- capture evidence;
- submit verification;
- see submission status.

## Reviewer

Optional separate role.

Can review evidence but cannot change system configuration.

---

# 8. INSPECTION WORKFLOW

Implement the following state machine:

```
CREATED
   ↓
ASSIGNED
   ↓
READY
   ↓
SESSION_STARTED
   ↓
CHALLENGES_IN_PROGRESS
   ↓
EVIDENCE_UPLOADING
   ↓
PROCESSING
   ↓
VERIFIED
   or
FLAGGED
   or
FAILED
   ↓
APPROVED / REJECTED

```

State transitions must be validated on the server.

Never rely exclusively on client-side state.

---

# 9. ACTIVE CHALLENGE-RESPONSE SYSTEM

This is the primary differentiating feature.

The server must generate unpredictable challenges only after the verification session begins.

Challenge information should include:

```
{
  "challengeId": "...",
  "sessionId": "...",
  "type": "ROTATE_RIGHT",
  "parameters": {
    "minimumDegrees": 30,
    "maximumDegrees": 50
  },
  "expiresAt": "...",
  "nonce": "..."
}

```

The client should not know future challenges ahead of time.

---

# 10. INITIAL CHALLENGE TYPES

Implement at least these challenges.

## Challenge A — Rotate Right

Instruction:

```
Rotate your phone approximately 40° to the right.

```

Validate using:

- gyroscope;
- rotation-vector sensor;
- visual optical flow.

---

## Challenge B — Rotate Left

Same as above in opposite direction.

---

## Challenge C — Tilt Down

Instruction:

```
Point the camera toward the ground.

```

Validate orientation change using:

- rotation vector;
- accelerometer;
- camera-frame movement.

---

## Challenge D — Tilt Up

Opposite of Tilt Down.

---

## Challenge E — Move Forward

Instruction:

```
Take approximately 2–3 steps forward.

```

Validate using:

- accelerometer;
- step-like motion;
- GPS movement if available;
- optical flow.

GPS should not be required for very small indoor movements.

---

## Challenge F — Move Closer

Instruction:

```
Move closer to the target object.

```

Validate using scene scale changes / optical flow.

Treat this as an advanced challenge.

---

# 11. CHALLENGE SECURITY

Challenges must:

- be generated server-side;
- contain a nonce;
- expire quickly;
- belong to exactly one session;
- not be reusable;
- be signed or integrity-protected;
- have server-controlled parameters;
- be completed within allowed timing windows.

Record:

```
challenge issued
challenge displayed
challenge started
challenge completed
sensor verification result
visual verification result
final challenge score

```

---

# 12. SENSOR CAPTURE

During a verification session collect synchronized data from:

- accelerometer;
- gyroscope;
- rotation vector;
- magnetometer where available;
- GPS/location;
- timestamps.

Each sensor reading should have:

```
{
  "sensorType": "GYROSCOPE",
  "timestampNs": 123456789,
  "x": 0.3,
  "y": 1.1,
  "z": 0.2,
  "accuracy": 3
}

```

Use monotonic timestamps where possible for synchronization.

Do NOT attempt to upload every raw sensor sample continuously to the backend.

Collect locally, compress/batch it, and upload session evidence efficiently.

---

# 13. CAMERA CAPTURE

Use CameraX.

During active verification:

- prevent gallery uploads;
- require live camera capture;
- record a short continuous sequence;
- timestamp frames or video relative to sensor stream;
- prevent switching to imported media;
- preserve session continuity.

Where practical, record:

- video;
- selected key frames;
- camera metadata;
- frame timestamps.

Do not record excessive video unnecessarily.

---

# 14. VISUAL-INERTIAL CONSISTENCY

This is one of SiteProof's strongest technical features.

Goal:

Determine whether movement visible in camera frames is broadly consistent with movement measured by the device's inertial sensors.

Example:

```
Gyroscope:
Phone rotated 42° right.

Computer vision:
Scene moved consistently with a right rotation.

Result:
CONSISTENT

```

versus:

```
Gyroscope:
Almost no physical movement.

Computer vision:
Large scene rotation visible.

Result:
SUSPICIOUS
Possible video replay or screen attack.

```

Implement using OpenCV.

Start with:

- feature detection;
- feature matching;
- optical flow;
- homography / affine transformation estimation.

Extract motion features such as:

- direction;
- magnitude;
- rotational pattern;
- frame-to-frame continuity.

Do not attempt full visual-inertial SLAM initially.

Build a practical consistency check.

---

# 15. SCENE CONTINUITY CHECK

The captured sequence should show continuous scene evolution.

Detect suspicious discontinuities such as:

- sudden unrelated frame;
- frozen video;
- duplicated frame sequence;
- abrupt scene replacement;
- extremely unnatural temporal changes.

Produce:

```
sceneContinuityScore: 0.0–1.0

```

Use classical CV initially.

Avoid unnecessary deep-learning complexity.

---

# 16. SCREEN / REPLAY ATTACK HEURISTICS

Implement experimental indicators for a user photographing another screen.

Do NOT claim perfect screen detection.

Possible signals:

- strong moiré patterns;
- display refresh artifacts;
- unusual rectangular boundaries;
- sensor-motion mismatch;
- scene motion inconsistent with phone motion;
- repetitive frame patterns;
- focus/reflection patterns.

Return:

```
replayRisk:
LOW / MEDIUM / HIGH

```

Clearly label this as a heuristic.

---

# 17. LOCATION VERIFICATION

Compare captured location against assigned inspection coordinates.

Inputs:

- latitude;
- longitude;
- reported accuracy;
- timestamp;
- geofence radius.

Use Haversine distance.

Example:

```
Expected radius:
100 m

Measured distance:
23 m

GPS accuracy:
8 m

Location result:
PASS

```

Do NOT blindly accept poor accuracy readings.

Example:

```
distance = 60 m
accuracy = ±900 m

Result:
INCONCLUSIVE

```

---

# 18. LOCATION SPOOFING RESILIENCE

Do not claim perfect GPS spoof detection.

Use multiple indicators:

- Android mock-location indicators where available;
- Play Integrity;
- unrealistic location jumps;
- impossible speeds;
- location timestamps;
- network/environment consistency;
- historical session pattern.

Return a risk signal rather than a binary claim.

---

# 19. WI-FI ENVIRONMENT FINGERPRINT

When Android permissions and OS restrictions allow, collect nearby Wi-Fi metadata.

Store privacy-conscious values such as:

- hashed BSSID;
- signal strength;
- channel/frequency;
- security capabilities.

Avoid storing SSIDs unnecessarily.

Create an environmental fingerprint:

```
AP_HASH_A   -52 dBm
AP_HASH_B   -67 dBm
AP_HASH_C   -73 dBm

```

Treat Wi-Fi only as supporting evidence.

Never make verification depend solely on Wi-Fi availability.

---

# 20. DEVICE INTEGRITY

Integrate Android Play Integrity when practical.

Send integrity token to backend.

Backend verifies token and stores result.

Possible result:

```
APP_INTEGRITY: PASS
DEVICE_INTEGRITY: PASS
LICENSE_STATUS: PASS

```

The project must still function in development environments where full production attestation may not be available.

Abstract the attestation provider behind an interface.

---

# 21. EVIDENCE HASHING

Every submitted evidence object must be hashed.

Use SHA-256.

Create hashes for:

- video;
- key frames;
- sensor package;
- location package;
- verification result;
- final report.

Create a manifest:

```
{
  "sessionId": "...",
  "files": [
    {
      "name": "capture.mp4",
      "sha256": "..."
    },
    {
      "name": "sensors.bin",
      "sha256": "..."
    }
  ]
}

```

---

# 22. SIGNED VERIFICATION RECEIPT

After verification, generate a signed server-side receipt.

Example payload:

```
{
  "inspectionId": "...",
  "sessionId": "...",
  "capturedAt": "...",
  "latitude": 22.5726,
  "longitude": 88.3639,
  "verificationScore": 92,
  "verdict": "VERIFIED",
  "manifestHash": "...",
  "issuedAt": "..."
}

```

Digitally sign the receipt using a server-side key.

Do not expose the private signing key.

Provide verification functionality for receipts.

---

# 23. VERIFICATION ENGINE

Create a modular verification engine.

Each verifier returns:

```
VerificationResult(
    status="PASS | FAIL | INCONCLUSIVE",
    score=0.0,
    confidence=0.0,
    reasons=[],
    metadata={}
)

```

Implement separate verifiers:

```
LocationVerifier
TimeVerifier
ChallengeVerifier
SensorVerifier
VisualMotionVerifier
SceneContinuityVerifier
DeviceIntegrityVerifier
EnvironmentVerifier
ReplayRiskVerifier

```

Then aggregate them.

---

# 24. INITIAL TRUST SCORE

Use deterministic scoring first.

Example:

```
Location verification       15
Time/session validity        10
Challenge completion        20
Sensor consistency          20
Visual-motion consistency   20
Scene continuity            10
Device/environment evidence  5
──────────────────────────────
TOTAL                       100

```

Suggested thresholds:

```
85–100
VERIFIED

65–84
REVIEW REQUIRED

0–64
FLAGGED

```

Do not hardcode these values throughout the application.

Store scoring policy in configuration.

---

# 25. EXPLAINABLE VERIFICATION

Every score must be explainable.

Bad:

```
Authenticity: 87%

```

Good:

```
Verification Score: 87/100

✓ Inspection location matched
✓ Session completed within allowed time
✓ All 3 randomized challenges completed
✓ Gyroscope movement matched visual motion

⚠ Wi-Fi evidence unavailable
⚠ Location accuracy was ±24 m

Replay Risk:
LOW

```

Judges and real users should understand WHY a submission was accepted or flagged.

---

# 26. OPTIONAL ML / AI LAYER

Do not force AI where deterministic methods are better.

After the deterministic system works, implement an optional anomaly-detection module.

Possible features:

```
gyro/visual rotation error
accelerometer/visual translation error
challenge completion duration
GPS confidence
frame continuity score
duplicate-frame ratio
motion smoothness
sensor timestamp irregularity

```

Use a lightweight model such as:

- Isolation Forest;
- One-Class SVM;
- simple statistical anomaly detection.

Train only on legitimate sessions collected during project testing.

This layer should provide an additional anomaly score.

Do not replace deterministic verification with opaque AI output.

---

# 27. ADMIN DASHBOARD

Build a clean dashboard.

## Main page

Display:

```
Active inspections
Pending reviews
Verified today
Flagged submissions
Average verification score

```

---

## Inspections list

Columns:

```
Inspection
Inspector
Location
Deadline
Status
Score
Created At

```

Provide filtering and search.

---

## Inspection details

Show:

```
Inspection ID
Assigned inspector
Expected location
Allowed radius
Deadline
Current state

```

Map:

```
Expected location
Captured location
Distance between them

```

---

# 28. VERIFICATION REPORT UI

Design a strong report screen.

Example:

```
SITEPROOF

Inspection #SP-1042
────────────────────────────────

Overall Verification
92 / 100
VERIFIED

Location
✓ PASS
23 m from assigned location

Session Time
✓ PASS

Random Challenges
✓ 3 / 3 completed

Sensor Consistency
✓ PASS
94%

Visual Motion
✓ PASS
91%

Scene Continuity
✓ PASS
96%

Replay Risk
LOW

Device Integrity
✓ PASS

Environment Signal
⚠ LIMITED

────────────────────────────────
Reviewer Decision

[ APPROVE ] [ REJECT ]

```

---

# 29. EVIDENCE TIMELINE

Create a timeline:

```
10:41:03 Session created
10:41:05 Device integrity checked
10:41:07 Location acquired
10:41:09 Challenge #1 issued
10:41:13 Challenge #1 passed
10:41:16 Challenge #2 issued
10:41:21 Challenge #2 passed
10:41:25 Final capture completed
10:41:31 Evidence uploaded
10:41:36 Verification completed

```

This is important for auditability.

---

# 30. DATABASE DESIGN

Create proper relational models for at least:

```
organizations
users
roles
inspectors
inspections
inspection_assignments
verification_sessions
challenges
challenge_results
sensor_packages
location_samples
evidence_files
verification_results
verification_signals
device_attestations
audit_logs
review_decisions
signed_receipts

```

Use UUIDs where appropriate.

Add:

- created\_at
- updated\_at

where relevant.

Add foreign keys and indexes.

Do not use JSON fields for everything.

Use JSON only for variable metadata.

---

# 31. API DESIGN

Use REST.

Example endpoints:

```
POST /auth/login

GET  /inspections
POST /inspections
GET  /inspections/{id}

POST /inspections/{id}/assign

POST /sessions
GET  /sessions/{id}

POST /sessions/{id}/challenge
POST /sessions/{id}/challenge/{challengeId}/complete

POST /sessions/{id}/evidence/initiate
POST /sessions/{id}/evidence/complete

GET /sessions/{id}/verification

POST /inspections/{id}/review

GET /reports/{id}

GET /receipts/{id}
POST /receipts/verify

```

Use OpenAPI documentation.

---

# 32. OFFLINE / UNSTABLE NETWORK SUPPORT

Field inspections may have poor internet connectivity.

Design the Android app so that:

- inspection assignment can be cached;
- active sensor collection works offline;
- captured evidence is stored securely locally;
- upload resumes when connectivity returns.

However:

Server-generated challenges should normally require a server connection to preserve unpredictability.

For future offline verification, consider downloading a signed challenge batch immediately before entering offline mode.

Do not implement complicated offline challenge batching until the normal online workflow works.

---

# 33. PRIVACY

Follow data-minimization principles.

Do not collect:

- contacts;
- unrelated photos;
- background audio;
- unnecessary device identifiers.

Clearly display what sensors are active.

Capture only during an explicit verification session.

Automatically stop collection when session ends.

Implement retention settings.

---

# 34. SECURITY REQUIREMENTS

Use:

- HTTPS;
- secure JWT handling;
- refresh-token rotation;
- password hashing using Argon2/bcrypt;
- rate limiting;
- authorization by role;
- server-side validation;
- signed upload URLs where possible;
- file-size limits;
- MIME validation;
- safe filenames;
- SQL injection protection;
- CSRF protection where applicable;
- audit logging.

Do NOT trust:

- client timestamps;
- client-generated trust scores;
- user-provided role fields;
- client-declared verification results.

The server makes the final trust decision.

---

# 35. THREAT MODEL

Document attacks including:

## Attack 1

Old photo submission.

Mitigation:

Live camera + unpredictable challenge.

## Attack 2

Prerecorded video displayed on another screen.

Mitigation:

Visual-inertial consistency + challenge-response + replay heuristics.

## Attack 3

GPS spoofing.

Mitigation:

Location risk checks + device integrity + environmental evidence.

## Attack 4

Modified application.

Mitigation:

Play Integrity + request signing.

## Attack 5

Evidence modified after capture.

Mitigation:

Cryptographic hashes + signed manifest.

## Attack 6

Replay previous valid submission.

Mitigation:

Unique session ID + nonce + one-time challenges + expiration.

## Attack 7

Network interception.

Mitigation:

TLS.

Document residual limitations.

---

# 36. DO NOT USE BLOCKCHAIN UNLESS JUSTIFIED

Do not add blockchain purely for presentation value.

Cryptographic hashing and signed receipts are sufficient for the base system.

If an immutable external audit ledger is eventually needed, design it as an optional future integration.

---

# 37. TESTING

Create meaningful automated tests.

## Backend unit tests

Test:

- Haversine calculation;
- score aggregation;
- state transitions;
- challenge expiration;
- nonce reuse prevention;
- report generation;
- permission checks;
- hashing;
- receipt verification.

## Verification tests

Create simulated signals for:

```
valid right rotation
wrong-direction rotation
insufficient movement
visual/sensor mismatch
expired challenge
wrong location
poor GPS confidence
duplicate evidence

```

## API integration tests

Cover:

```
login
inspection creation
assignment
session creation
challenge workflow
upload completion
verification
review

```

---

# 38. ATTACK TEST SUITE

Explicitly create demonstration scenarios.

## Scenario A — Genuine capture

Expected:

```
VERIFIED

```

## Scenario B — Existing image

Expected:

```
REJECTED / cannot participate in live challenge

```

## Scenario C — Video on laptop screen

Expected:

```
visual/sensor mismatch
HIGH replay risk

```

## Scenario D — Wrong location

Expected:

```
location verification fails

```

## Scenario E — Failed challenge

Expected:

```
challenge verification fails

```

## Scenario F — Modified evidence file

Expected:

```
hash verification fails

```

---

# 39. PERFORMANCE REQUIREMENTS

The Android application should:

- avoid unnecessary battery drain;
- collect sensors only during active sessions;
- avoid memory-heavy full-resolution frame processing;
- use appropriate background threads/coroutines;
- gracefully handle low-end Android devices.

Backend verification should process normal evidence within a reasonable period.

Target prototype processing time:

```
< 15 seconds

```

for a short verification session where hardware permits.

---

# 40. UI/UX REQUIREMENTS

Do not create a generic template-looking UI.

Android workflow should be extremely clear.

Example:

```
Inspection #SP-1024

You are within the required area ✓

Ready for verification.

Verification takes approximately
30–60 seconds.

[ START VERIFICATION ]

```

During challenge:

```
CHALLENGE 2 OF 3

↻

ROTATE YOUR PHONE
TO THE RIGHT

Keep the site visible.

████████░░

```

After:

```
Challenge completed ✓

Checking movement...

```

Do not expose raw technical sensor information to ordinary inspectors.

---

# 41. PROJECT REPOSITORY

Use a monorepo:

```
siteproof/
│
├── android/
│
├── backend/
│
├── web/
│
├── docs/
│
├── infrastructure/
│
├── scripts/
│
├── docker-compose.yml
├── .env.example
├── README.md
└── LICENSE

```

---

# 42. DOCUMENTATION

Create:

```
README.md
docs/architecture.md
docs/threat-model.md
docs/api.md
docs/verification-engine.md
docs/mobile-sensors.md
docs/deployment.md
docs/testing.md

```

README must contain:

- project overview;
- architecture;
- screenshots;
- local setup;
- environment configuration;
- demo workflow;
- testing instructions.

---

# 43. DEVELOPMENT APPROACH

DO NOT generate the entire project blindly in one step.

Build incrementally.

Before writing major code:

1. inspect existing repository;
2. describe intended changes;
3. create/update implementation plan;
4. implement one cohesive milestone;
5. run tests;
6. fix failures;
7. update documentation;
8. commit logical changes if Git commits are permitted.

Never leave important functionality as:

```
TODO
mock
fake data
placeholder
coming soon

```

unless explicitly marked as a future feature.

---

# 44. DEVELOPMENT PHASES

## Phase 1 — Foundation

Build:

- monorepo;
- Docker Compose;
- PostgreSQL;
- backend skeleton;
- web dashboard skeleton;
- Android application skeleton;
- authentication.

Acceptance:

All three components run locally.

---

## Phase 2 — Inspection Management

Build:

- organizations;
- users;
- inspectors;
- inspection CRUD;
- assignment workflow;
- dashboard.

Acceptance:

Admin can create and assign an inspection.

Inspector sees assignment on Android.

---

## Phase 3 — Live Capture

Build:

- CameraX;
- GPS;
- accelerometer;
- gyroscope;
- synchronized session recording.

Acceptance:

Android generates a session evidence package.

---

## Phase 4 — Challenge Engine

Implement:

- server challenge generation;
- rotate-left;
- rotate-right;
- tilt-down;
- challenge expiration;
- challenge logging.

Acceptance:

At least three unpredictable challenges work end-to-end.

---

## Phase 5 — Sensor Verification

Verify:

- rotation angle;
- direction;
- challenge timing;
- basic motion.

Acceptance:

Correct movement passes.

Wrong movement fails.

---

## Phase 6 — Computer Vision

Implement:

- key-frame extraction;
- optical flow;
- visual rotation estimation;
- scene continuity.

Acceptance:

Backend produces visual motion metrics.

---

## Phase 7 — Sensor Fusion

Compare:

```
visual motion
vs
inertial motion

```

Generate consistency score.

Acceptance:

Real movement produces high consistency.

Screen/video replay demonstration produces significantly lower consistency.

---

## Phase 8 — Verification Engine

Combine all signals into explainable trust score.

Acceptance:

Report clearly explains scoring.

---

## Phase 9 — Evidence Security

Implement:

- SHA-256 manifest;
- signed receipt;
- immutable audit events.

Acceptance:

Modified evidence fails integrity validation.

---

## Phase 10 — Advanced Signals

Add where feasible:

- Wi-Fi fingerprint;
- Play Integrity;
- replay-risk heuristics;
- anomaly detection.

---

## Phase 11 — Polish

Complete:

- responsive dashboard;
- reports;
- map;
- reviewer workflow;
- error handling;
- loading states;
- accessibility;
- documentation.

---

# 45. MVP DEFINITION

The MVP MUST successfully demonstrate:

```
Admin creates inspection
        ↓
Inspector receives inspection
        ↓
Inspector reaches location
        ↓
SiteProof starts live verification
        ↓
Server sends random challenge
        ↓
Android records camera + sensors
        ↓
Inspector completes challenge
        ↓
Evidence uploaded
        ↓
Backend analyzes signals
        ↓
Trust score generated
        ↓
Admin reviews verification report

```

Until this flow works reliably, do not spend significant time on optional features.

---

# 46. FINAL PROJECT ACCEPTANCE CRITERIA

Project is considered complete only when:

### Functional

- admin can create inspection;
- inspection can be assigned;
- inspector receives it;
- location is checked;
- live session starts;
- randomized challenges work;
- camera and sensor data are synchronized;
- evidence uploads successfully;
- backend analyzes evidence;
- verification score is generated;
- evidence integrity is checked;
- admin can review submission;
- audit history is visible.

### Technical

- Android app runs on a real Android device;
- backend runs through Docker;
- PostgreSQL is persistent;
- web dashboard works;
- APIs are documented;
- automated tests exist;
- no hardcoded secrets;
- errors are handled;
- project can be reproduced from README.

### Demonstration

The team can demonstrate:

```
1. Genuine inspection → VERIFIED

2. Wrong movement → FLAGGED

3. Wrong location → FLAGGED

4. Replay/video-on-screen attempt
   → visual/inertial inconsistency

5. Evidence modification
   → hash failure

```

---

# 47. FINAL-YEAR PROJECT REQUIREMENT

This must remain realistic for a six-member B.Tech final-year team.

Prefer:

```
correct engineering
+
clearly explained algorithms
+
working prototype

```

over:

```
many unfinished advanced features

```

Every major technical decision should be explainable during a viva.

Avoid black-box complexity that the team cannot defend.

---

# 48. CODE QUALITY

Follow:

- SOLID where appropriate;
- clean modular architecture;
- meaningful naming;
- small functions;
- type safety;
- structured error handling;
- dependency injection where useful;
- configuration through environment variables;
- no duplicated business logic;
- no giant controller/service classes.

Write comments explaining **why**, not obvious syntax.

---

# 49. IMPORTANT AGENT BEHAVIOUR

Whenever implementing a phase:

1. inspect the repository first;
2. identify what already exists;
3. provide a short implementation plan;
4. implement fully;
5. run relevant builds/tests;
6. inspect failures;
7. fix them;
8. report exactly what changed;
9. state what remains;
10. do not claim success unless builds/tests actually pass.

Do not silently skip requirements.

If a requested API is restricted by Android/browser/device limitations, clearly explain the limitation and implement the closest robust alternative.

Never fabricate successful sensor readings, device attestation results, test results, or security guarantees.

---

# 50. FIRST TASK

Begin only with **Phase 1: Foundation**.

Before writing code:

1. propose the final directory structure;
2. define component boundaries;
3. define database entities at a high level;
4. define API boundaries;
5. define Android architecture;
6. define web architecture;
7. define local Docker architecture;
8. identify major technical risks.

Then implement Phase 1.

After Phase 1 is working and tested, stop and provide:

- files created;
- commands to run;
- tests performed;
- architecture decisions;
- known issues;
- exact recommended Phase 2 tasks.

Do NOT automatically proceed to all later phases in a single pass.