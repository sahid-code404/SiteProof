# SiteProof Handover — Phase 2

Phase 2 implements inspection management and assignment. Do not start Phase 3 until CI is green and the manual Android physical-device acceptance flow in `docs/testing.md` has been completed.

## Implemented boundary

- organization-aware users/inspectors/inspections;
- Alembic migrations;
- admin inspection CRUD, assignment/reassignment/cancellation;
- assignment history and audit events;
- inspector-only list/detail access;
- `ASSIGNED → ACKNOWLEDGED → READY` server-controlled transitions;
- real React admin UI;
- real Android Retrofit/StateFlow assignment workflow with read-only offline cache.

## Explicitly not implemented

- CameraX live capture;
- sensor collection;
- randomized challenges;
- verification sessions/evidence upload;
- computer vision, replay heuristics or trust scoring.

## Before Phase 3

1. Review the Phase 2 pull request and CI results.
2. Run `docker compose up --build` on a development workstation.
3. Complete the physical-device Android flow.
4. Fix any environment/device-specific problems.
5. Update `PROJECT_STATE.md` to confirm Phase 2 acceptance.
6. Only then begin live camera + sensor acquisition.
