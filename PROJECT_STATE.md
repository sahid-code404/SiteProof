# SiteProof Project State

Current Phase:
Phase 2 — Inspection Management

Current Milestone:
2.12 End-to-End Acceptance — COMPLETE

Last Completed:
2.12 End-to-End Acceptance — physical Android + real local backend/PostgreSQL acceptance passed on 2026-08-19

Build Status:

Backend:
PASS — CI run #283 passed fresh PostgreSQL migration, Phase 2 downgrade/re-upgrade, Ruff, and pytest after the Android isolation fix.

Web:
PASS — CI run #283 passed tests, lint, and production build.

Android:
PASS — CI run #283 passed Android unit tests and debug APK assembly. CI run #285 built the replacement physical-device APK configured for `192.168.1.102`; the real-device acceptance flow completed successfully.

Infrastructure:
PASS (LOCAL SETUP OBSERVED) — web, backend, PostgreSQL 16, and MinIO were observed running on 2026-08-19; backend and PostgreSQL reported healthy.

Database:
PASS — PostgreSQL-backed Phase 2 migrations are covered by CI; the local acceptance PostgreSQL container was observed healthy and the real acceptance audit trail was queried successfully.

Acceptance Status:
**PASS — PHASE 2 COMPLETE**

Observed real acceptance:
- corrected seed migration completed successfully against the existing PostgreSQL volume;
- direct admin login returned HTTP 200;
- admin manually created `Phase 2 Final Test` and assigned Inspector One;
- the physical Android device authenticated and received the assignment;
- Inspector One changed the inspection from `ASSIGNED` → `ACKNOWLEDGED` → `READY`;
- the refreshed web dashboard persisted `ACKNOWLEDGED`;
- `READY` persisted after fully closing and reopening the Android app;
- Inspector Two account-switch isolation passed on the fixed APK with `No inspections assigned.`;
- admin assignment history showed Inspector One as the active assignment;
- direct backend/PostgreSQL audit query returned, in order, `INSPECTION_CREATED`, `INSPECTION_ASSIGNED`, `INSPECTION_ACKNOWLEDGED`, and `INSPECTION_READY` for inspection `bfa76c9d-898e-443a-ab96-065f37c16627`.

Resolved acceptance defects:
- `@siteproof.local` demo addresses conflicted with the real email-validation contract; migrated to `@siteproof.example.com`.
- reseeding an existing database initially collided with inspector employee-code uniqueness; the seed now migrates legacy identities in place and is idempotent.
- Android account switching retained the prior inspector's in-memory list; authenticated navigation/ViewModel state is now session-scoped and the physical retest passed.

Known non-blocking information:
- physical handset model: NOT RECORDED;
- Android version: NOT RECORDED;
- no values are inferred or fabricated for those fields.

Next earliest incomplete gate:
**Phase 3 — Live Capture, Location & Multi-Sensor Evidence Collection: real-device acceptance on branch `phase3/live-capture`.**

Phase 3 automated code already exists in a stacked draft PR, but its real-device acceptance remains open. The next acceptance must prove one real CameraX capture plus real sensor/location evidence, app-private evidence packaging, offline retention/retry, upload to the backend, and admin evidence display. Do not treat Phase 4+ acceptance as complete until the earlier physical gates are closed.
