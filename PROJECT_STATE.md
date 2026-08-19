# SiteProof Project State

Current Phase:
Phase 2 — Inspection Management

Current Milestone:
2.12 End-to-End Acceptance — Physical Android Device

Last Completed:
2.11 Audit Events — implemented and covered by automated tests

Build Status:

Backend:
PASS — latest generic CI run #271 passed fresh PostgreSQL migration, Phase 2 downgrade/re-upgrade, Ruff, and pytest.

Web:
PASS — latest generic CI run #271 passed tests, lint, and production build.

Android:
PASS (AUTOMATED) — latest generic CI run #271 passed Android unit tests and debug APK assembly. A separate CI build (#268) also produced the physical-device APK configured for `192.168.1.102`.

Infrastructure:
PASS (LOCAL SETUP OBSERVED) — on 2026-08-19 the web, backend, PostgreSQL 16, and MinIO containers were observed running; backend and PostgreSQL reported healthy.

Database:
PASS — PostgreSQL-backed Phase 2 migrations are covered by CI; the local acceptance PostgreSQL container was observed healthy.

Acceptance Status:
PARTIAL — REAL DEVICE FLOW REACHED READY; FINAL CHECKS REMAIN

Known Issues:
- RESOLVED AND RETESTED: the former `@siteproof.local` seed accounts were rejected by current email validation. The seed now uses/migrates to `@siteproof.example.com`, local reseeding succeeded, and direct admin login returned HTTP 200.
- The physical Android app authenticated against the real local backend, loaded the assigned `Verify repaired pothole` inspection, and reached `READY` on the user's real phone.
- Phase 2.12 still requires explicit evidence for manual admin inspection creation, unrelated-inspector isolation, direct `ACKNOWLEDGED` observation, `READY` persistence after refresh/restart, assignment history, and audit records.
- Phase 3 and later branches exist, but under the execution-controller rules they must not be treated as completed until this earliest outstanding acceptance milestone is closed.
- `main` remains behind the stacked phase branches; do not merge/advance later phases while this acceptance gate is unresolved.

Next Task:
- Finish the remaining Phase 2.12 acceptance checks listed in `docs/device-testing.md`.
- Record only actual observations from the real web/backend/Android flow.
- If every remaining item passes, mark Phase 2.12 PASS, update `docs/implementation-log.md`, and only then evaluate Phase 3.16 real-device acceptance.
