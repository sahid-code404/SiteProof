# SiteProof

**SiteProof — Active Multi-Sensor Proof-of-Physical-Presence and Tamper-Resistant Field Verification System**

SiteProof is a full-stack field-inspection platform with a React admin dashboard, FastAPI/PostgreSQL backend, and native Android inspector app. Development is incremental and each phase has an explicit security boundary.

## Current Phase 5 development capability

Phase 5 extends the Phase 4 active challenge system with **independent camera-side visual-motion analysis**:

```text
Admin creates + assigns inspection
  → Inspector ACKNOWLEDGES
  → Inspector marks READY
  → Android starts one continuous CameraX + sensor + GPS capture
  → server reveals one unpredictable rotate/tilt challenge at a time
  → Phase 4 independently validates the physical phone movement from sensors
  → app packages continuous video + full sensor/location data + challenge timeline
  → WorkManager uploads and the backend SHA-256 verifies the evidence
  → Phase 5 maps each challenge window onto the continuous video timeline
  → OpenCV samples derived frames at configurable FPS/resolution
  → Shi-Tomasi + Lucas-Kanade track visual features
  → RANSAC estimates dominant global scene motion
  → backend stores visual direction, approximate magnitude, confidence and continuity
  → reviewer sees sensor evidence and visual evidence in separate sections
```

Supported challenge types remain:

```text
ROTATE_LEFT
ROTATE_RIGHT
TILT_UP
TILT_DOWN
```

**Phase 5 does not claim final authenticity.** It measures camera/scene motion independently. It deliberately does not compare that motion with Phase 4 gyroscope/rotation-vector evidence. Sensor-camera consistency and contradiction detection belong to Phase 6.

## Visual-motion pipeline

The first deterministic CV implementation uses classical, viva-explainable algorithms:

```text
continuous video
  ↓
challenge/video timestamp mapping
  ↓
configurable padded frame window
  ↓
downscale + grayscale
  ↓
ORB feature-quality count
  ↓
grid-distributed Shi-Tomasi points
  ↓
Lucas-Kanade sparse optical flow
  ↓
forward/backward track filtering
  ↓
RANSAC partial-affine global motion
  ↓
optional homography diagnostic
  ↓
visual direction + approximate magnitude
  ↓
confidence + continuity + duplicate/freeze metrics
```

Low-feature, blurred or otherwise unreliable scenes return `INCONCLUSIVE` rather than a fabricated movement result.

## Repository structure

```text
siteproof/
├── android/                 # Kotlin + Jetpack Compose inspector app
├── backend/                 # FastAPI + SQLAlchemy + Alembic + OpenCV
├── web/                     # React + TypeScript admin/reviewer dashboard
├── docs/
├── infrastructure/
├── scripts/
├── .github/workflows/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick start

```bash
cp .env.example .env
# Change JWT_SECRET and local passwords.
docker compose up --build
```

Open:

- Admin dashboard: `http://localhost:5173`
- OpenAPI: `http://localhost:8000/docs`
- Backend health: `http://localhost:8000/health`
- Optional MinIO console: `http://localhost:9001`

The default development storage backend writes evidence outside PostgreSQL into the `evidence_data` Docker volume. S3-compatible/MinIO storage is also supported through configuration. Phase 5 retrieves uploaded video internally and uses secure temporary files for OpenCV when materialization is required; it does not create permanent public evidence URLs for analysis.

## Seed local users

```bash
export SITEPROOF_DEMO_ADMIN_PASSWORD='choose-a-local-password'
export SITEPROOF_DEMO_INSPECTOR_PASSWORD='choose-another-password'
cd backend
python ../scripts/seed_phase2.py
```

## Backend development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

Checks:

```bash
pytest -q
ruff check app tests alembic
```

The challenge API is documented in `docs/api.md`, Phase 4 sensor math/security in `docs/challenge-engine.md`, and Phase 5 CV math/coordinate conventions in `docs/visual-motion-analysis.md`.

## Web development

```bash
cd web
npm install
npm test
npm run lint
npm run build
npm run dev
```

The inspection detail page shows two deliberately separate reviewer sections:

```text
LIVE CHALLENGES · SENSOR EVIDENCE
VISUAL MOTION ANALYSIS · CAMERA EVIDENCE
```

It does not calculate or display a sensor-camera consistency percentage. The page still states **Final authenticity: Not yet calculated**.

## Android development

Open `android/` in Android Studio. For a physical phone, put the phone and development machine on the same LAN and build with the machine's LAN address:

```bash
gradle :app:assembleDebug \
  -PSITEPROOF_API_BASE_URL=http://192.168.1.20:8000/api/v1/
```

The app requests camera and fine/coarse location only for live verification. It does **not** request microphone permission; CameraX recording contains no audio. The verification Activity is portrait-locked so initial rotate/tilt coordinate semantics are defined consistently.

CameraX never restarts between challenges. The evidence metadata records `videoStartRelativeNs` plus challenge issued/started/completed timestamps relative to the same monotonic capture anchor, allowing the backend to locate each Phase 5 video window without changing the Phase 3 video format.

Challenge guidance asks for a slow, smooth movement while keeping the site visible. This helps reduce motion blur while intentionally not exposing algorithm thresholds.

## Real-device and real-video acceptance are mandatory

Automated CI can validate migrations, APIs and deterministic synthetic CV behavior, but it cannot prove that a real SiteProof Android camera recording produces reliable visual motion estimates.

Before Phase 5 can be called accepted, perform real SiteProof captures and record actual results in `docs/testing.md`. Required validation includes:

1. Create/assign an inspection and complete the live Phase 4 challenge sequence on a physical Android phone.
2. Confirm one continuous `capture.mp4` spans all challenges and uploads through the normal evidence pipeline.
3. Confirm the backend decodes the actual uploaded file and independently derives codec, dimensions, FPS, duration and frame count.
4. Confirm each real challenge maps to the correct video interval.
5. Test legitimate ROTATE_RIGHT, ROTATE_LEFT, TILT_UP and TILT_DOWN motions across multiple real backgrounds.
6. Record actual `SUCCESS`, `INCONCLUSIVE` and wrong-direction rates; do not fabricate them.
7. Include low-light/motion-blur/low-feature cases and confirm the analyzer can return `INCONCLUSIVE` instead of fake certainty.
8. Record actual processing duration and memory observations where practical.
9. Confirm the reviewer dashboard shows camera-side visual evidence while final authenticity and sensor-camera consistency remain uncalculated.

Phase 4 physical sensor validation is also still a prerequisite; Phase 5 does not retroactively prove Phase 4 hardware behavior.

## Phase boundary

Phase 5 intentionally does **not** implement:

- gyroscope-vs-video comparison;
- visual-inertial consistency scoring;
- final replay-risk classification;
- overall SiteProof trust score;
- VERIFIED / FLAGGED authenticity verdicts;
- Play Integrity or Wi-Fi fingerprinting;
- anomaly-detection ML.

Those are later phases. Do not start Phase 6 until real Phase 5 video acceptance has been recorded.

## Documentation

- `docs/architecture.md`
- `docs/api.md`
- `docs/inspection-lifecycle.md`
- `docs/live-capture.md`
- `docs/evidence-format.md`
- `docs/session-lifecycle.md`
- `docs/challenge-engine.md`
- `docs/visual-motion-analysis.md`
- `docs/testing.md`
- `docs/project-spec.md`
