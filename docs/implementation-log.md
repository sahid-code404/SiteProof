# SiteProof Implementation Log

## 2026-08-19 — Execution-controller recovery audit / Phase 2.12

Implemented / recorded:
- Inspected the live repository, phase branches, Phase 2 PR, Phase 3 PR, and current Phase 9 draft PR.
- Confirmed the repository had advanced into stacked later-phase branches while the Phase 2 physical-device acceptance gate was still explicitly open.
- Identified **Phase 2.12 — End-to-End Acceptance** as the earliest incomplete milestone under the execution-controller rules.
- Restored `PROJECT_STATE.md` to a milestone-oriented status format.
- Added `docs/device-testing.md` so hardware results can be recorded without inventing values.

Tests / build evidence reviewed:
- Phase 2 exact head before the recovery documentation commit: `78d1dfb18806cd44888d44b5fe2022b47cb37106`.
- GitHub CI run #9: completed successfully.
- Fresh recovery CI run #252 on `518d50e9d92341ee7359bf0c509defe64a482620`: completed successfully.
- Backend: fresh PostgreSQL migration PASS; Phase 2 downgrade/re-upgrade PASS; Ruff PASS; `pytest -q` 14 passed on run #252.
- Web: Vitest 5 passed; ESLint PASS; production build PASS on run #252.
- Android: unit-test task PASS; `:app:assembleDebug` PASS on run #252.

Acceptance:
- Physical Android device flow: **NOT TESTED YET**.
- No device model, Android version, phone-network result, Android login result, or final lifecycle result is claimed here.

## 2026-08-19 — Phase 2.12 local acceptance defect: seed email rejected

Observed during real local acceptance setup:
- Fedora host LAN address observed as `192.168.1.102`.
- Docker stack observed running: web, FastAPI backend, PostgreSQL 16, and MinIO.
- Backend and PostgreSQL containers reported healthy; the backend health endpoint was reachable.
- `scripts/seed_phase2.py` successfully created the original demo accounts.
- Direct login with `admin@siteproof.local` returned HTTP 422 before password authentication.
- Backend validation detail reported that `.local` is a special-use/reserved domain and is not accepted by the current email validator.

Root cause:
- The seed script generated `@siteproof.local` addresses while the real login request schema uses Pydantic `EmailStr`. The development seed contract therefore disagreed with the production login contract.

Fix implemented:
- Replaced seed emails with login-schema-compatible addresses under `siteproof.example.com`.
- Added `backend/tests/test_phase2_seed_contract.py` to load the real seed constants and validate every demo address with the real `LoginRequest` schema.
- Updated `docs/device-testing.md` with the Docker-based seed procedure, minimum password length, current demo email addresses, and the actual setup observations made so far.
- Kept the milestone open; web login and the physical Android lifecycle must be retested after pulling the fix.

Automated verification:
- CI run #256 on code head `b8e71f6215e8dd0655316ff1a7a1d04f77340f05` passed PostgreSQL fresh migration, downgrade/re-upgrade, Ruff, and **15 backend tests** including the new seed/login contract test.
- Web tests/lint/build also passed on run #256.
- Final full-branch CI must be checked on the latest documentation head before treating the automated gate as current.

Current acceptance status:
- **IMPLEMENTED — HARDWARE TEST PENDING**.
- Seed/login defect: fixed in code, user retest pending.
- Physical Android admin → inspector → ACKNOWLEDGE → READY acceptance: not completed yet.

## 2026-08-19 — Phase 2.12 seed migration fix and real-device progress

Additional defect found during retest:
- After changing demo emails from `.local` to `.example.com`, rerunning the seed against an already-seeded PostgreSQL volume attempted to create new inspector users while reusing existing employee codes such as `SP-I001`.
- PostgreSQL correctly raised the `uq_inspector_employee_code` unique constraint and rolled back the seed transaction.

Fix implemented:
- Updated the Phase 2 seed to migrate existing legacy demo users in place instead of creating duplicate identities.
- Existing inspector profile IDs and employee codes are preserved.
- Demo passwords are refreshed during reseeding.
- Added regression coverage for migration from a legacy `.local` seed state and repeated idempotent execution.

Automated verification:
- Backend CI passed with **16 tests** after the migration fix.
- Generic full CI run #271 on restored workflow head `3a9e5c1530aa2a50077f47201b155dc0061f299f` passed backend migration/downgrade, Ruff, pytest, web tests/lint/build, and Android unit-test/debug assembly.
- CI run #268 produced a debug APK configured specifically for the acceptance host `http://192.168.1.102:8000/api/v1/`; the temporary workflow customization was removed afterward.

Observed real-device acceptance progress:
- Corrected seed rerun completed successfully against the user's existing PostgreSQL volume.
- Direct admin login returned HTTP 200 with an ADMIN token.
- Web UI showed `Verify repaired pothole` assigned to Inspector One in `ASSIGNED` state.
- The physical Android app authenticated against the real local backend and displayed the assigned inspection.
- The physical Android screenshot showed the inspection in `READY` state with `Verification ready`.
- Because the backend only permits `mark_ready` from `ACKNOWLEDGED`, the successful `READY` state confirms that the acknowledge transition succeeded during the real flow.

Still required before closing Phase 2.12:
- Demonstrate manual admin inspection creation rather than relying only on the seeded inspection.
- Verify unrelated inspector work is not visible.
- Capture a direct web/API observation of `ACKNOWLEDGED` if required by the acceptance checklist.
- Restart/refresh and confirm `READY` persists.
- Verify assignment history.
- Verify audit records for assignment, acknowledgement, and ready transitions.

Current acceptance status:
- **PARTIAL — REAL DEVICE FLOW REACHED READY; FINAL ACCEPTANCE CHECKS REMAIN**.
