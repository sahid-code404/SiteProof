# SiteProof

**SiteProof — Active Multi-Sensor Proof-of-Physical-Presence and Tamper-Resistant Field Verification System**

SiteProof is a full-stack field-inspection platform with a React admin dashboard, FastAPI/PostgreSQL backend, and native Android inspector app. Development is incremental and each phase has an explicit security boundary.

## Current Phase 4 capability

The Phase 3 continuous live-evidence pipeline is extended with unpredictable server-generated phone-movement challenges:

```text
Admin creates + assigns inspection
  → Inspector ACKNOWLEDGES
  → Inspector marks READY
  → Android checks fresh GPS + sensor capabilities
  → server creates short-lived verification session
  → CameraX + sensors + GPS start one continuous capture
  → server reveals Challenge #1 only
  → inspector rotates/tilts phone
  → Android submits only that synchronized sensor window
  → backend independently returns PASS / FAIL / INCONCLUSIVE
  → server reveals next unpredictable challenge
  → required challenge sequence finishes
  → app packages video + full sensors + GPS + challenge timeline
  → WorkManager uploads evidence
  → admin sees challenge results + evidence receipt status
```

Supported Phase 4 movement types:

```text
ROTATE_LEFT
ROTATE_RIGHT
TILT_UP
TILT_DOWN
```

**Phase 4 does not claim final scene authenticity.** It can verify that the phone moved consistently with a requested sensor challenge, but it does not yet compare that physical movement with the external camera scene. OpenCV optical flow, visual-inertial consistency, replay detection and overall trust scoring belong to later phases.

## Repository structure

```text
siteproof/
├── android/                 # Kotlin + Jetpack Compose inspector app
├── backend/                 # FastAPI + SQLAlchemy + Alembic
├── web/                     # React + TypeScript admin dashboard
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

The default development storage backend writes evidence outside PostgreSQL into the `evidence_data` Docker volume. S3-compatible/MinIO storage is also supported through configuration.

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

The challenge API is documented in `docs/api.md` and the sensor math/security design in `docs/challenge-engine.md`.

## Web development

```bash
cd web
npm install
npm test
npm run lint
npm run build
npm run dev
```

The inspection detail page shows per-challenge result/score/sensor metrics for authorized admin review, but deliberately displays **Final authenticity: Not yet calculated**.

## Android development

Open `android/` in Android Studio. For a physical phone, put the phone and development machine on the same LAN and build with the machine's LAN address:

```bash
gradle :app:assembleDebug \
  -PSITEPROOF_API_BASE_URL=http://192.168.1.20:8000/api/v1/
```

The app requests camera and fine/coarse location only for live verification. It does **not** request microphone permission; CameraX recording contains no audio. The verification Activity is portrait-locked so initial rotate/tilt coordinate semantics are defined consistently.

During Phase 4, CameraX never restarts between challenges. Full motion/location evidence remains in the Phase 3 package while only a short raw sensor slice is sent for immediate challenge validation. Future challenges are not preloaded. If connectivity disappears during a current challenge submission, its evidence is preserved locally and the app waits for reconnection before any next challenge.

## Phase 4 real-device test is mandatory

Automated CI cannot prove real gyroscope direction, rotation-vector behavior or CameraX continuity. Before Phase 4 can be called accepted, test at least one physical Android phone and record actual results in `docs/testing.md`.

Required device demo:

1. Create/assign an inspection and mark it READY.
2. Start live verification and confirm one continuous rear-camera recording begins.
3. Receive only Challenge #1, physically perform it, and receive the backend sensor result.
4. Confirm Challenge #2 is unknown until Challenge #1 finishes; repeat through Challenge #3.
5. Include at least one deliberately wrong movement and confirm the backend records the actual result.
6. Confirm capture finalizes/uploads and the admin dashboard displays the challenge timeline plus video/sensors/location/manifest status.
7. Verify the dashboard still says final authenticity is not calculated.
8. Record real legitimate/wrong-motion trial counts; do not fabricate them.

## Documentation

- `docs/architecture.md`
- `docs/api.md`
- `docs/inspection-lifecycle.md`
- `docs/live-capture.md`
- `docs/evidence-format.md`
- `docs/session-lifecycle.md`
- `docs/challenge-engine.md`
- `docs/testing.md`
- `docs/project-spec.md`
