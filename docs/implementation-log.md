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

## 2026-08-19 — Phase 2.12 inspector account-switch isolation defect

Observed on physical device:
- The user signed out from Inspector One and authenticated as Inspector Two.
- The Inspector Two `My Inspections` list still displayed the prior `Verify repaired pothole` card from Inspector One.
- Opening that card returned `HTTP 404 Not Found`.

Root cause:
- Server-side assignee scoping was correct: Inspector Two was denied the detail resource.
- Android already cleared its persisted inspection cache on login/logout, but the Compose navigation graph and `InspectionsViewModel` survived the account switch and retained Inspector One's in-memory list state.

Fix implemented:
- Added `InspectionRepository.sessionScopeKey()`, based on a SHA-256 fingerprint of the current access token. The raw token is not logged or persisted by this session-scoping mechanism.
- Scoped the authenticated `NavHost`, inspection-list ViewModel, and inspection-detail ViewModels to that authentication-session key so an account switch creates fresh UI state and disposes the previous inspector graph.
- Kept the existing persisted cache clearing behavior on both login and logout.
- Added Android unit tests proving account logins produce different session scopes, login clears the previous inspection cache, and logout clears both session and cache state.

Automated verification:
- Full CI run #283 passed backend migration/downgrade, Ruff, pytest, web tests/lint/build, Android unit tests, and debug APK assembly.
- CI run #285 built and uploaded a replacement debug APK configured for `http://192.168.1.102:8000/api/v1/` with the isolation fix.
- The CI workflow was restored to its generic build configuration immediately afterward.

Acceptance status:
- **PARTIAL — FIX IMPLEMENTED; PHYSICAL ISOLATION RETEST PENDING**.
- Phase 2.12 remains open until Inspector Two no longer sees Inspector One's inspection and the remaining acceptance checks are completed.

## 2026-08-19 — Phase 2.12 isolation retest, manual create, and acknowledge

Observed on physical device:
- The replacement isolation-fix APK passed the Inspector One -> sign out -> Inspector Two retest. Inspector Two showed `No inspections assigned.` and no longer displayed Inspector One's stale inspection card.
- A fresh inspection named `Phase 2 Final Test` was manually created through the admin flow and assigned to Inspector One.
- Inspector One's Android list showed both the existing `Verify repaired pothole` in `READY` and the new `Phase 2 Final Test` in `ASSIGNED`.
- Opening the new inspection showed the `ACKNOWLEDGE` action.
- After tapping `ACKNOWLEDGE`, the same physical-device detail screen showed status `ACKNOWLEDGED` and exposed the `MARK READY` action.

Acceptance impact:
- PASS — unrelated-inspector isolation on the fixed APK.
- PASS — manual admin inspection creation and delivery to the assigned inspector.
- PASS — direct Android `ACKNOWLEDGE` transition observation.
- Still pending — separate web/API observation while `Phase 2 Final Test` remains `ACKNOWLEDGED`, READY persistence after full app restart/refresh, assignment history, and audit records.

Current acceptance status:
- **PARTIAL — MANUAL CREATE, ASSIGNMENT, ISOLATION, AND ANDROID ACKNOWLEDGE PASSED; FINAL ACCEPTANCE CHECKS REMAIN**.

## 2026-08-19 — Phase 2.12 final physical acceptance

Final observations:
- The admin web dashboard showed `Phase 2 Final Test` as `ACKNOWLEDGED` after the Android acknowledge action, confirming backend/database persistence.
- Inspector One marked `Phase 2 Final Test` as `READY` on the physical Android device.
- SiteProof was fully closed and reopened; the inspection still showed `READY` with `Verification ready`, confirming restart persistence.
- The admin inspection detail showed `Inspector One` in `ASSIGNMENT HISTORY` as the active assignment with the recorded assignment timestamp.
- A direct query through the running backend against the real local PostgreSQL database found exactly four audit records for inspection `bfa76c9d-898e-443a-ab96-065f37c16627`, in chronological order:
  - `INSPECTION_CREATED`
  - `INSPECTION_ASSIGNED`
  - `INSPECTION_ACKNOWLEDGED`
  - `INSPECTION_READY`
- The `INSPECTION_ASSIGNED` audit metadata identified the assigned inspector as `e7d63042-b8b3-479a-9973-14da6d11a177`.

Final acceptance result:
- **PASS — Phase 2.12 complete.**
- **PASS — Phase 2 Inspection Management complete under the execution-controller acceptance rule.**

Next earliest incomplete gate:
- **Phase 3 — Live Capture, Location & Multi-Sensor Evidence Collection real-device acceptance** on branch `phase3/live-capture`.
- Phase 3 must next prove one real CameraX capture, real sensor/location evidence, app-private packaging, temporary-offline retention/retry, backend upload, and admin evidence display.
- Phase 4 and later real-device acceptance remain blocked behind Phase 3.

No handset model or Android-version value is invented; those remain NOT RECORDED for this Phase 2 acceptance run.
