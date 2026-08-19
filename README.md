# SiteProof

**SiteProof — Active Multi-Sensor Proof-of-Physical-Presence and Tamper-Resistant Field Verification System**

SiteProof is a full-stack field-inspection platform with a React admin dashboard, FastAPI/PostgreSQL backend, and a native Android inspector app. Development is incremental and every phase has an explicit security boundary.

## Current Phase 3 capability

The current branch extends the Phase 2 inspection workflow with live Android evidence collection:

```text
Admin creates + assigns inspection
  → Inspector ACKNOWLEDGES
  → Inspector marks READY
  → Android checks fresh GPS + device sensors
  → Server creates short-lived verification session
  → CameraX records rear-camera video
  → accelerometer/gyroscope/rotation-vector + GPS record on one monotonic timeline
  → app builds and SHA-256 hashes an evidence package
  → WorkManager reliably uploads evidence
  → backend independently hashes + structurally validates files
  → admin sees Evidence Uploaded / Awaiting Verification
```

**Phase 3 does not claim that evidence is verified or authentic.** Random challenges, optical flow, replay detection and trust scoring belong to later phases.

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

The default development storage backend writes evidence outside PostgreSQL into the `evidence_data` Docker volume. An S3-compatible/MinIO adapter is also available by setting `STORAGE_BACKEND=s3`.

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

## Web development

```bash
cd web
npm install
npm test
npm run lint
npm run build
npm run dev
```

## Android development

Open `android/` in Android Studio. For a physical phone, put the phone and development machine on the same LAN and build with the machine's LAN address:

```bash
gradle :app:assembleDebug \
  -PSITEPROOF_API_BASE_URL=http://192.168.1.20:8000/api/v1/
```

The debug manifest permits cleartext HTTP only for local development. Release configuration keeps cleartext disabled. The app requests `CAMERA` and fine/coarse location only when the inspector enters live verification; it does **not** request microphone permission and CameraX recording is created without audio.

Live evidence stays in app-private storage. It is not written to Gallery, Downloads or DCIM. Pending evidence remains local across temporary network failures and WorkManager retries it when connectivity returns. Successfully uploaded local evidence is removed after backend confirmation.

## Phase 3 real-device test

Phase 3 is not complete on emulator/CI alone. Use at least one real Android phone and execute:

1. Admin creates and assigns an inspection with the phone physically inside the configured radius.
2. Inspector logs into Android, taps **ACKNOWLEDGE**, then **MARK READY**.
3. Tap **START LIVE VERIFICATION**, grant camera/location permissions, and confirm fresh GPS/capability status.
4. Record at least 8 seconds (15–30 seconds recommended) while moving the phone naturally.
5. Stop capture and confirm the app reports evidence saved/uploading.
6. Temporarily disconnect the phone after capture; confirm evidence remains pending locally, then restore network and allow WorkManager to finish.
7. On the admin inspection page confirm Video, Motion sensors, Location data and Manifest are received and the message says **Awaiting verification analysis**.
8. Inspect the development evidence package and confirm sensor/location values are real and varying.

Record the actual device/Android version and pass/fail observations in `docs/testing.md`. Never fabricate this report.

## Documentation

- `docs/architecture.md`
- `docs/api.md`
- `docs/inspection-lifecycle.md`
- `docs/live-capture.md`
- `docs/evidence-format.md`
- `docs/session-lifecycle.md`
- `docs/testing.md`
- `docs/project-spec.md`
