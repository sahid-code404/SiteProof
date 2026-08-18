# SiteProof

**SiteProof — Active Multi-Sensor Proof-of-Physical-Presence and Tamper-Resistant Field Verification System**

This repository is the Phase 1 foundation for the SiteProof final-year B.Tech project. It is intentionally incremental: the foundation is created first, then inspection management, live capture, challenges, verification, and evidence security are layered on top.

## Phase 1 contents

- FastAPI backend with health endpoint, PostgreSQL integration, JWT authentication primitives, SQLAlchemy models, and tests.
- React + TypeScript + Vite dashboard shell with a backend health check and login-ready API client.
- Android Kotlin + Jetpack Compose application shell with clean package boundaries for future camera/sensor work.
- Docker Compose for PostgreSQL, FastAPI, web dashboard, and MinIO.
- GitHub Actions for backend tests and frontend build/lint.
- Architecture, risks, handover, and Phase 2 planning docs.

## Repository structure

```text
siteproof/
├── android/
├── backend/
├── web/
├── docs/
├── infrastructure/
├── scripts/
├── .github/workflows/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick start

1. Copy environment variables:

```bash
cp .env.example .env
```

2. Start the backend, database, web app, and MinIO:

```bash
docker compose up --build
```

3. Open:

- Web dashboard: http://localhost:5173
- Backend API docs: http://localhost:8000/docs
- Backend health: http://localhost:8000/health
- MinIO console: http://localhost:9001

## Local development without Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

### Web

```bash
cd web
npm install
npm run dev
```

### Android

Open the `android/` folder in Android Studio. The repository intentionally does not commit generated Gradle wrapper binaries. Use Android Studio's Gradle sync, then run the `app` configuration on an emulator or physical device.

## Development rule

Do not jump directly to advanced anti-replay or AI features. Complete one cohesive milestone, run tests/builds, fix failures, update docs, and only then continue.

See `docs/HANDOVER.md` before beginning Phase 2.
