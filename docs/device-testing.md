# SiteProof Device Testing

This document records **actual physical-device results only**. Never replace missing hardware evidence with emulator assumptions, synthetic measurements, or guessed values.

## Phase 2.12 — Inspection Assignment End-to-End Acceptance

Status: **PARTIAL — ACKNOWLEDGED PERSISTENCE PASSED; FINAL CHECKS REMAIN**

### Device / environment

Device:
Physical Android handset — model NOT RECORDED

Android version:
NOT RECORDED

SiteProof APK/build:
- Initial Phase 2 debug APK built by GitHub CI run #268 for `http://192.168.1.102:8000/api/v1/`.
- Replacement isolation-fix APK built successfully by GitHub CI run #285 for the same host URL; physical account-switch retest passed.

Host machine LAN IP:
192.168.1.102 — observed during the 2026-08-19 acceptance setup

Phone and host on same network:
PASS — the installed Android app authenticated against the host backend and loaded the assigned inspection.

Backend health before test:
PASS — local backend was reachable on port 8000 during acceptance setup

PostgreSQL/Docker stack status:
PASS — web, backend, PostgreSQL 16, and MinIO containers were observed running; backend and PostgreSQL reported healthy

### Setup

1. Copy the environment template and set local secrets:

```bash
cp .env.example .env
```

2. Start the real local stack:

```bash
docker compose up --build
```

3. Seed Phase 2 development accounts inside the backend container. Demo passwords must be at least 12 characters:

```bash
docker compose cp scripts/seed_phase2.py backend:/tmp/seed_phase2.py

docker compose exec \
  -e SITEPROOF_DEMO_ADMIN_PASSWORD='choose-a-local-password-12+' \
  -e SITEPROOF_DEMO_INSPECTOR_PASSWORD='choose-another-password-12+' \
  backend python /tmp/seed_phase2.py
```

The current seed accounts use login-schema-compatible example-domain addresses:

- Admin: `admin@siteproof.example.com`
- Inspector One: `inspector1@siteproof.example.com`
- Inspector Two: `inspector2@siteproof.example.com`
- Inspector Three: `inspector3@siteproof.example.com`

Do not use the former `@siteproof.local` seed addresses. Current `email-validator` releases reject `.local` as a special-use domain before password authentication.

4. Determine the development host's LAN address and build/install the Android debug app with the physical-device API URL, for example:

```bash
cd android
gradle :app:assembleDebug \
  -PSITEPROOF_API_BASE_URL=http://<HOST-LAN-IP>:8000/api/v1/
```

Use the actual reachable LAN IP. Do not use the emulator-only `10.0.2.2` address on a physical phone.

### Acceptance checklist

Record PASS / FAIL and notes for every item after actually performing it.

| Check | Result | Actual observation |
|---|---|---|
| Docker/PostgreSQL/backend/web stack starts | PASS | Web, backend, PostgreSQL, and MinIO containers observed running on 2026-08-19. |
| Backend `/health` is reachable | PASS | Local backend health endpoint responded during setup. |
| Admin can log into web dashboard | PASS | Corrected seeded admin authenticated successfully; direct API login returned HTTP 200 and the admin inspection dashboard was subsequently displayed. |
| Admin can create an inspection | PASS | A fresh inspection named `Phase 2 Final Test` was manually created through the admin flow and subsequently appeared on the real Android device with its configured coordinates, radius, deadline, type, and priority. |
| Admin can assign Inspector One | PASS | Web screenshot showed `Verify repaired pothole` in `ASSIGNED` state with active assignment `Inspector One`; the manually created `Phase 2 Final Test` also appeared under Inspector One as `ASSIGNED`. |
| Physical Android device can log in as assigned inspector | PASS | Physical-device screenshots show Inspector One authenticated against the real backend. |
| Assigned inspection appears on Android | PASS | Both the seeded `Verify repaired pothole` and manually created `Phase 2 Final Test` appeared on the physical Android device for Inspector One. |
| Unrelated inspector work is not visible | PASS | On the replacement isolation-fix APK, Inspector Two's physical-device list showed `No inspections assigned.` after the Inspector One -> sign out -> Inspector Two account switch. The prior Inspector One card was no longer visible. |
| **ACKNOWLEDGE** succeeds | PASS | The manually created `Phase 2 Final Test` was shown as `ASSIGNED` with an `ACKNOWLEDGE` action, then a physical-device screenshot immediately after the action showed status `ACKNOWLEDGED` and the `MARK READY` action. |
| Web/backend persist `ACKNOWLEDGED` | PASS | After the Android acknowledgement, the refreshed admin web inspection list showed `Phase 2 Final Test` with status `ACKNOWLEDGED`, confirming the state persisted through the backend/database rather than existing only in Android UI memory. |
| **MARK READY** succeeds | PASS | Physical-device screenshot shows the earlier `Verify repaired pothole` inspection in `READY` with `Verification ready`. |
| `READY` persists after refresh/restart | NOT TESTED | Restart/refresh persistence has not yet been explicitly observed for `Phase 2 Final Test`. |
| Assignment history is correct | NOT TESTED | |
| Audit records are present and correct | NOT TESTED | |

### Account-switch isolation defect

Observed behavior before fix:
- Inspector Two's list showed an inspection that belonged to Inspector One.
- The detail request returned HTTP 404 for Inspector Two.

Interpretation:
- Server-side tenant/assignee scoping remained effective; unauthorized detail access was blocked.
- The Android Compose navigation/view-model graph retained the previous inspector's in-memory list state after logout/login.

Fix implemented:
- Added a per-authentication session scope key derived from a SHA-256 fingerprint of the active access token; the token itself is not logged or persisted by this mechanism.
- Recreated the authenticated navigation graph and list/detail ViewModels when the inspector session changes.
- Existing persisted inspection cache clearing on login/logout remains in place.
- Added Android unit coverage proving account logins create different session scopes and that logout clears session/cache state.

Automated verification:
- Full CI run #283 passed backend, web, Android unit tests, and Android debug APK assembly after the isolation fix.
- Physical-device replacement APK build #285 passed Android tests/build and uploaded the host-specific APK.

Physical retest:
- PASS — user-provided physical-device screenshot on 2026-08-19 shows Inspector Two with an empty inspection list and the message `No inspections assigned.` after the account-switch sequence.

### Manual-create / acknowledge observation

Physical-device screenshots on 2026-08-19 show:
- Inspector One's list containing the manually created `Phase 2 Final Test` in `ASSIGNED` state.
- The detail screen for `Phase 2 Final Test` in `ASSIGNED` state with the `ACKNOWLEDGE` control.
- The same inspection immediately afterward in `ACKNOWLEDGED` state with the `MARK READY` control.
- A subsequent refreshed admin web screenshot shows `Phase 2 Final Test` as `ACKNOWLEDGED`, closing the server/database persistence check for this transition.

### Acceptance result

Overall result:
**PARTIAL — MANUAL CREATE, ASSIGNMENT, ISOLATION, AND ACKNOWLEDGED PERSISTENCE PASSED; FINAL ACCEPTANCE CHECKS REMAIN**

Blocking defect(s):
- RESOLVED AND RETESTED — former `@siteproof.local` seed addresses were rejected by login validation. The seed now migrates legacy demo identities to `@siteproof.example.com`; local reseeding succeeded and admin login returned HTTP 200.
- RESOLVED AND RETESTED — stale Inspector One list state was visible after switching to Inspector Two. Backend authorization had already blocked detail access; the Android session-scoped UI state fix now passes physical retest, with Inspector Two showing no unrelated inspection.
- OPEN ACCEPTANCE ITEMS — `READY` persistence after refresh/restart, assignment history, and audit verification.

Evidence recorded by:
User-observed local acceptance setup, user-provided web/Android screenshots, direct backend login result, and repository/CI verification

Test date/time:
2026-08-19

### Rule for closing Phase 2.12

Only change the overall result to PASS after the complete physical-device flow has been run against the real backend/PostgreSQL stack and every required observation above has been recorded. If any required step fails, keep the milestone open, record the exact failure, fix it, rerun the relevant tests, and repeat the device flow.
