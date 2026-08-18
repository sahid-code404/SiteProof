# SiteProof Handover

## Current milestone

Phase 1 — Foundation.

## What exists

- Monorepo layout.
- Docker Compose services for PostgreSQL, backend, web, and MinIO.
- FastAPI backend with configuration, SQLAlchemy base models, health endpoint, authentication primitives, and tests.
- React/TypeScript dashboard shell connected to backend health.
- Kotlin/Jetpack Compose Android shell.
- Architecture and technical-risk documentation.
- GitHub Actions baseline.

## Important implementation rule

Before changing code in a future session:

1. inspect the repository and current branch;
2. read `docs/project-spec.md` and this file;
3. run current tests/builds;
4. describe the cohesive milestone being implemented;
5. implement it fully;
6. rerun tests/builds and fix failures;
7. update docs and this handover;
8. report exactly what changed and what remains.

## Exact next milestone: Phase 2 — Inspection Management

Implement in this order:

1. Introduce Alembic migrations and remove Phase-1 `create_all` bootstrap.
2. Add organization membership / user-organization relation.
3. Add inspector profile model.
4. Add inspection and inspection-assignment models with UUIDs, timestamps, indexes, and validated statuses.
5. Add admin authorization dependencies.
6. Add inspection CRUD APIs.
7. Add assignment API.
8. Add seed/bootstrap command for the first development admin.
9. Add web login page, authenticated shell, inspection list/create/detail flows.
10. Add Android login and assigned-inspections list.
11. Add backend unit and API integration tests for role permissions, creation, assignment, and invalid transitions.
12. Update API/architecture docs.

## Do not start yet in Phase 2

- CameraX recording
- sensor fusion
- OpenCV
- challenge scoring
- Play Integrity
- Wi-Fi fingerprinting
- AI/anomaly detection

Those belong to later phases after inspection assignment works end-to-end.
