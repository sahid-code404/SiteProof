# SiteProof

**SiteProof — Active Multi-Sensor Proof-of-Physical-Presence and Tamper-Resistant Field Verification System**

SiteProof is a full-stack field-inspection platform with a React admin/reviewer dashboard, FastAPI/PostgreSQL backend, and native Android inspector app. Development is incremental and every phase has an explicit security boundary.

## Current Phase 6 development capability

Phase 6 extends the existing active challenge and visual-motion system with deterministic **visual–inertial cross-signal consistency**:

```text
Admin creates + assigns inspection
  → Inspector ACKNOWLEDGES and marks READY
  → Android starts one continuous CameraX + sensor + GPS capture
  → server reveals one unpredictable rotate/tilt challenge at a time
  → Phase 4 independently validates physical phone motion from sensors
  → evidence uploads and SHA-256 hashes are verified
  → Phase 5 independently estimates camera/scene movement from video
  → Phase 6 normalizes both measurements to physical-camera semantics
  → direction + angle + timing + duration + motion-curve shape are compared
  → backend stores consistency, confidence and structured mismatch reasons
  → reviewer sees sensor, camera and cross-signal evidence as distinct layers
```

Supported primary challenge types remain:

```text
ROTATE_LEFT
ROTATE_RIGHT
TILT_UP
TILT_DOWN
```

Phase 6 can return:

```text
CONSISTENT
PARTIALLY_CONSISTENT
MISMATCH
INCONCLUSIVE
```

**These are not final SiteProof authenticity verdicts.** The overall trust score and final `VERIFIED` / `REVIEW REQUIRED` decision belong to Phase 7.

## Fusion pipeline

```text
Phase 4 sensor result
  angle + direction + confidence
          +
verified sensors.ndjson.gz
  high-rate gyro timing curve
          +
Phase 5 visual result
  angle + direction + timing + motion curve
          ↓
common MotionEstimate normalization
          ↓
direction comparison
angle/magnitude comparison
start/end timing comparison
duration comparison
          ↓
independent curve normalization
20 Hz common resampling
Pearson correlation
±500 ms limited-lag cross-correlation
          ↓
confidence-aware weighted consistency
          ↓
structured mismatch reasons
```

The default component weights are direction 25%, magnitude 25%, timing 20%, correlation 20%, duration 10%. All prototype thresholds and weights are typed configuration and must be tuned from real-device measurements.

Low-quality input returns `INCONCLUSIVE` instead of turning missing evidence into an accusation.

High-confidence contradictions can identify patterns such as:

```text
OPPOSITE_DIRECTION
VISUAL_WITHOUT_SENSOR_MOTION
SENSOR_WITHOUT_VISUAL_MOTION
```

Phase 6 does not label those patterns “fake video” or “replay confirmed.”

## Repository structure

```text
siteproof/
├── android/                 # Kotlin + Jetpack Compose inspector app
├── backend/                 # FastAPI + SQLAlchemy + Alembic + OpenCV/NumPy
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

Evidence is stored outside PostgreSQL. Local volume storage is the default development adapter; S3-compatible/MinIO storage is supported through configuration.

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

Phase 4 sensor math is documented in `docs/challenge-engine.md`, Phase 5 camera motion in `docs/visual-motion-analysis.md`, and Phase 6 fusion in `docs/visual-inertial-fusion.md`.

## Web development

```bash
cd web
npm install
npm test
npm run lint
npm run build
npm run dev
```

The inspection detail page now separates:

```text
LIVE CHALLENGES · SENSOR EVIDENCE
VISUAL MOTION ANALYSIS · CAMERA EVIDENCE
CROSS-SIGNAL ANALYSIS · PHYSICAL VS CAMERA
```

The third section presents sensor/camera direction and angle side by side, angle difference, signed timing offsets, limited-lag motion correlation, consistency score, fusion confidence, structured reasons and a lightweight normalized timeline graph.

The page still states **Final authenticity: Not yet calculated**.

## Android development

Open `android/` in Android Studio. For a physical phone, put the phone and development machine on the same LAN and build with the development machine's LAN address:

```bash
gradle :app:assembleDebug \
  -PSITEPROOF_API_BASE_URL=http://192.168.1.20:8000/api/v1/
```

CameraX still records continuously across the whole challenge sequence. Sensors and video use the existing common monotonic capture anchor; Phase 6 does not introduce a new Android clock or rebuild the Phase 3 capture format.

## Phase 6 API

Authorized `ADMIN` / `REVIEWER` users can retrieve:

```text
GET /api/v1/sessions/{sessionId}/fusion-analysis
```

and request current-version reanalysis:

```text
POST /api/v1/sessions/{sessionId}/fusion-analysis/retry
```

Current fusion version:

```text
fusion-v1.0
```

## Real-device and controlled-attack acceptance are mandatory

Automated tests can validate deterministic fusion math and pipeline behavior, but they cannot prove real sensor-camera accuracy or attack detection.

Before Phase 6 can be called accepted, record actual SiteProof Android results including:

1. at least one genuine randomized challenge where real sensor and video evidence produce a defensible `CONSISTENT` result;
2. at least one controlled video-on-screen scenario where visible motion without matching physical motion produces a defensible inconsistency where expected;
3. repeated legitimate right/left/up/down trials where practical;
4. real angle-error, timing-offset and correlation distributions;
5. threshold tuning from legitimate measurements rather than arbitrary pass/fail adjustment;
6. device model, Android version, sensor availability and camera FPS;
7. actual fusion processing time and multiple Android devices where available.

Do not fabricate measurements if a test behaves differently from expectation.

## Security boundary and limitations

Phase 6 makes simple visual/sensor contradictions observable, but does not make SiteProof mathematically impossible to spoof.

Residual risks include physically synchronized replay, manipulated sensors/OS, instrumented devices, rolling shutter, low light, motion blur, textureless scenes, systematic camera/sensor latency, monocular angle approximation, and screen scenarios where real phone motion also produces corresponding visual motion.

Replay/screen classification, device integrity, environment signals and the final explainable trust engine remain later phases.

## Documentation

- `docs/architecture.md`
- `docs/api.md`
- `docs/inspection-lifecycle.md`
- `docs/live-capture.md`
- `docs/evidence-format.md`
- `docs/session-lifecycle.md`
- `docs/challenge-engine.md`
- `docs/visual-motion-analysis.md`
- `docs/visual-inertial-fusion.md`
- `docs/testing.md`
- `docs/project-spec.md`
