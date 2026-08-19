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
PASS (AUTOMATED + ISOLATION RETEST) — CI run #283 passed Android unit tests and debug APK assembly with the account-switch isolation fix. CI run #285 built the replacement physical-device APK configured for `192.168.1.102`, and the real-phone account-switch isolation retest passed.

Infrastructure:
PASS (LOCAL SETUP OBSERVED) — on 2026-08-19 the web, backend, PostgreSQL 16, and MinIO containers were observed running; backend and PostgreSQL reported healthy.

Database:
PASS — PostgreSQL-backed Phase 2 migrations are covered by CI; the local acceptance PostgreSQL container was observed healthy.

Acceptance Status:
PARTIAL — ACCOUNT-SWITCH ISOLATION PASSED; FINAL CHECKS REMAIN

Known Issues:
- RESOLVED AND RETESTED: the former `@siteproof.local` seed accounts were rejected by current email validation. The seed now uses/migrates to `@siteproof.example.com`, local reseeding succeeded, and direct admin login returned HTTP 200.
- The physical Android app authenticated against the real local backend, loaded the assigned `Verify repaired pothole` inspection, and reached `READY` on the user's real phone.
- RESOLVED AND RETESTED: after switching from Inspector One to Inspector Two, the old Android build retained Inspector One's stale inspection card. Server authorization already blocked detail access with HTTP 404. The authenticated Compose navigation/ViewModel graph is now session-scoped, and the replacement APK physical retest showed Inspector Two with `No inspections assigned.`
- Phase 2.12 still requires explicit evidence for manual admin inspection creation, direct `ACKNOWLEDGED` observation, `READY` persistence after refresh/restart, assignment history, and audit records.
- Phase 3 and later branches exist, but under the execution-controller rules they must not be treated as completed until this earliest outstanding acceptance milestone is closed.
- `main` remains behind the stacked phase branches; do not merge/advance later phases while this acceptance gate is unresolved.

Next Task:
- Manually create a fresh inspection in the admin web UI and assign it to Inspector One.
- On the physical Android device, acknowledge the new inspection and capture a direct web observation while it is `ACKNOWLEDGED` before marking it ready.
- Mark it `READY`, fully close/reopen the Android app and refresh to prove persistence.
- Verify assignment history and audit records for the test inspection.
- If every remaining item passes, mark Phase 2.12 PASS, update `docs/implementation-log.md`, and only then evaluate Phase 3.16 real-device acceptance.
