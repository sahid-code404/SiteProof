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
PASS (AUTOMATED + REAL-DEVICE ACCEPTANCE IN PROGRESS) — CI run #283 passed Android unit tests and debug APK assembly with the account-switch isolation fix. CI run #285 built the replacement physical-device APK configured for `192.168.1.102`; physical account-switch isolation, manual inspection delivery, Android acknowledgement, and web-backed acknowledgement persistence have now passed.

Infrastructure:
PASS (LOCAL SETUP OBSERVED) — on 2026-08-19 the web, backend, PostgreSQL 16, and MinIO containers were observed running; backend and PostgreSQL reported healthy.

Database:
PASS — PostgreSQL-backed Phase 2 migrations are covered by CI; the local acceptance PostgreSQL container was observed healthy.

Acceptance Status:
PARTIAL — ACKNOWLEDGED PERSISTENCE PASSED; FINAL CHECKS REMAIN

Known Issues:
- RESOLVED AND RETESTED: the former `@siteproof.local` seed accounts were rejected by current email validation. The seed now uses/migrates to `@siteproof.example.com`, local reseeding succeeded, and direct admin login returned HTTP 200.
- The physical Android app authenticated against the real local backend, loaded the assigned `Verify repaired pothole` inspection, and reached `READY` on the user's real phone.
- RESOLVED AND RETESTED: after switching from Inspector One to Inspector Two, the old Android build retained Inspector One's stale inspection card. Server authorization already blocked detail access with HTTP 404. The authenticated Compose navigation/ViewModel graph is now session-scoped, and the replacement APK physical retest showed Inspector Two with `No inspections assigned.`
- PASSED: a new inspection named `Phase 2 Final Test` was manually created through the admin flow, appeared for Inspector One on the real Android device in `ASSIGNED`, changed to `ACKNOWLEDGED` after the Android action, and the refreshed admin web dashboard also showed `ACKNOWLEDGED`, confirming backend/database persistence.
- Phase 2.12 still requires explicit `READY` persistence after refresh/restart, assignment-history verification, and audit-record verification.
- Phase 3 and later branches exist, but under the execution-controller rules they must not be treated as completed until this earliest outstanding acceptance milestone is closed.
- `main` remains behind the stacked phase branches; do not merge/advance later phases while this acceptance gate is unresolved.

Next Task:
- On Android, mark `Phase 2 Final Test` as `READY`.
- Fully close SiteProof, reopen it, refresh, and confirm `Phase 2 Final Test` still shows `READY`.
- Verify assignment history and audit records for `Phase 2 Final Test`.
- If every remaining item passes, mark Phase 2.12 PASS, update `docs/implementation-log.md`, and only then evaluate Phase 3.16 real-device acceptance.
