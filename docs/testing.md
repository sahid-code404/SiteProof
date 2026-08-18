# Testing

## Backend

Install development dependencies and run:

```bash
cd backend
pytest -q
ruff check app tests alembic
```

The Phase 2 suite covers:

- health and password/JWT security primitives;
- inspection creation and editing;
- latitude/longitude/radius/deadline validation;
- same-organization assignment;
- inactive and cross-organization assignment rejection;
- inspector isolation;
- unauthorized assignment rejection;
- reassignment with history preservation;
- acknowledge and ready transitions;
- invalid transitions and cancellation;
- cancelled-inspection assignment rejection;
- pagination/filtering and real dashboard counts;
- inspector creation/listing;
- the full admin → inspector → acknowledge → ready API flow with audit events.

## Migrations

Local SQLite compatibility check:

```bash
DATABASE_URL=sqlite:////tmp/siteproof-migration.db alembic upgrade head
DATABASE_URL=sqlite:////tmp/siteproof-migration.db alembic downgrade 0001_phase1_baseline
DATABASE_URL=sqlite:////tmp/siteproof-migration.db alembic upgrade head
```

CI additionally runs migrations against PostgreSQL 16, which is the target database.

## Web

```bash
cd web
npm test
npm run lint
npm run build
```

Vitest covers client-side inspection validation. Build/lint protect the routed dashboard, assignment UI and Leaflet integration.

## Android

CI uses Gradle with Java 17:

```bash
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

Repository unit tests cover successful assignment fetch, cached offline fallback, empty-cache network failure, acknowledge cache update and ready cache update.

Final Phase 2 acceptance still requires a manual run on a physical Android device against the real backend/PostgreSQL stack.

## Manual Phase 2 flow

1. Start `docker compose up --build`.
2. Create/seed an organization admin and inspector.
3. Login to the web dashboard.
4. Create a real inspection and assign the inspector.
5. Login on the Android app as that inspector.
6. Verify the inspection is visible and unrelated inspectors' work is not.
7. Tap **ACKNOWLEDGE** and verify both Android/web/backend show `ACKNOWLEDGED`.
8. Tap **MARK READY** and verify `READY` persists after refresh/restart.
9. Inspect assignment history and database audit records.
