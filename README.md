# SiteProof

**SiteProof — Active Multi-Sensor Proof-of-Physical-Presence and Tamper-Resistant Field Verification System**

SiteProof is a final-year B.Tech project that builds stronger field-verification evidence from multiple independent signals. Development is intentionally incremental. **Phase 2 implements inspection management and assignment only; live camera capture, sensors, challenge-response, computer vision and verification scoring are not part of this phase.**

## Phase 2 capability

A real end-to-end data flow now exists:

```text
Admin login
  → create inspection + site/radius/deadline
  → assign or reassign an organization inspector
  → inspector logs into Android
  → assigned inspection appears
  → inspector acknowledges
  → inspector explicitly marks READY
```

The backend enforces organization isolation and state transitions. Assignment history and server-side audit events are preserved.

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

1. Create your local environment file:

```bash
cp .env.example .env
```

2. Change `JWT_SECRET` and any local passwords in `.env`.

3. Start PostgreSQL, the backend, web dashboard and MinIO:

```bash
docker compose up --build
```

The backend container runs `alembic upgrade head` before starting FastAPI.

4. Open:

- Admin dashboard: `http://localhost:5173`
- OpenAPI: `http://localhost:8000/docs`
- Backend health: `http://localhost:8000/health`
- MinIO console: `http://localhost:9001`

## Create local users

Create one administrator after migrations:

```bash
cd backend
python ../scripts/seed_admin.py \
  "SiteProof Demo Authority" \
  admin@example.com \
  "Demo Admin" \
  "your-local-password"
```

Or seed the optional Phase 2 demo dataset. Passwords are supplied via environment variables and are never embedded in application code:

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

Tests and lint:

```bash
pytest -q
ruff check app tests alembic
```

## Web development

```bash
cd web
npm install
npm run dev
```

Checks:

```bash
npm test
npm run lint
npm run build
```

The inspection form uses Leaflet/OpenStreetMap. Clicking the map updates latitude/longitude without a paid map API.

## Android development

Open `android/` in Android Studio, or use a compatible Gradle installation. The default **debug** API URL is the Android emulator host alias:

```text
http://10.0.2.2:8000/api/v1/
```

Override it for a physical device on your LAN:

```bash
gradle :app:assembleDebug \
  -PSITEPROOF_API_BASE_URL=http://192.168.1.20:8000/api/v1/
```

The debug manifest permits cleartext HTTP for local development. The main/release manifest disables cleartext traffic. JWTs stored by the Android app are encrypted using Android Keystore AES-GCM.

## Phase 2 demo

1. Sign into the web dashboard as an admin.
2. Create **Verify repaired pothole** with coordinates, radius, deadline and priority.
3. Open the inspection and assign an active inspector.
4. Sign into the Android app as that inspector.
5. Confirm only that inspector's assignments appear.
6. Open the inspection and tap **ACKNOWLEDGE**.
7. Tap **MARK READY**.
8. Refresh the web dashboard and confirm the persisted `READY` state and assignment history.

## Documentation

- `docs/architecture.md`
- `docs/api.md`
- `docs/inspection-lifecycle.md`
- `docs/testing.md`
- `docs/project-spec.md`

## Development rule

Do not begin live camera/sensor work until Phase 2 acceptance is complete. See `PROJECT_STATE.md`.
