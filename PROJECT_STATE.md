# SiteProof Project State

Current Phase:
Phase 2 — Inspection Management

Current Milestone:
2.12 End-to-End Acceptance — Physical Android Device

Last Completed:
2.11 Audit Events — implemented and covered by automated tests

Build Status:

Backend:
PASS — CI run #283 passed fresh PostgreSQL migration, Phase 2 downgrade/re-upgrade, Ruff, and pytest after the Android isolation fix.

Web:
PASS — CI run #283 passed tests, lint, and production build.

Android:
PASS (AUTOMATED) — CI run #283 passed Android unit tests and debug APK assembly with the account-switch isolation fix. CI run #285 also built and uploaded the replacement physical-device APK configured for `192.168.1.102`.

Infrastructure:
PASS (LOCAL SETUP OBSERVED) — on 2026-08-19 the web, backend, PostgreSQL 16, and MinIO containers were observed running; backend and PostgreSQL reported healthy.

Database:
PASS — PostgreSQL-backed Phase 2 migrations are covered by CI; the local acceptance PostgreSQL container was observed healthy.

Acceptance Status:
PARTIAL — ACCOUNT-SWITCH ISOLATION FIX RETEST PENDING

Known Issues:
- RESOLVED AND RETESTED: the former `@siteproof.local` seed accounts were rejected by current email validation. The seed now uses/migrates to `@siteproof.example.com`, local reseeding succeeded, and direct admin login returned HTTP 200.
- The physical Android app authenticated against the real local backend, loaded the assigned `Verify repaired pothole` inspection, and reached `READY` on the user's real phone.
- OBSERVED DEFECT, FIX IMPLEMENTED, RETEST PENDING: after switching from Inspector One to Inspector Two, the Android list retained Inspector One's stale inspection card. Opening it returned HTTP 404, confirming server-side authorization blocked Inspector Two while the Android UI leaked stale in-memory list state. The authenticated Compose navigation/ViewModel graph is now session-scoped and automated CI is green.
- Phase 2.12 still requires successful physical retest of unrelated-inspector isolation plus explicit evidence for manual admin inspection creation, direct `ACKNOWLEDGED` observation, `READY` persistence after refresh/restart, assignment history, and audit records.
- Phase 3 and later branches exist, but under the execution-controller rules they must not be treated as completed until this earliest outstanding acceptance milestone is closed.
- `main` remains behind the stacked phase branches; do not merge/advance later phases while this acceptance gate is unresolved.

Next Task:
- Install the replacement isolation-fix APK from CI run #285 and repeat the Inspector One -> sign out -> Inspector Two test.
- Inspector Two must not display Inspector One's inspection in the list. If it does, keep Phase 2.12 open and fix the remaining defect.
- After isolation passes, finish the remaining Phase 2.12 checks in `docs/device-testing.md`.
- Record only actual observations from the real web/backend/Android flow.
- If every remaining item passes, mark Phase 2.12 PASS, update `docs/implementation-log.md`, and only then evaluate Phase 3.16 real-device acceptance.
