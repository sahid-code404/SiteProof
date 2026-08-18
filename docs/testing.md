# Testing

## Backend

```bash
cd backend
pip install -e '.[dev]'
pytest -q
ruff check app tests
```

## Web

```bash
cd web
npm install
npm run build
npm run lint
```

## Docker smoke test

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
```

## Android

Open `android/` in Android Studio, sync Gradle, and run the app on an Android API 26+ emulator/device. Phase 1 does not yet exercise camera or sensors.
