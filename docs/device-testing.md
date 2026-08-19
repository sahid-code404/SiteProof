# SiteProof Device Testing

This document records **actual physical-device results only**. Never replace missing hardware evidence with emulator assumptions, synthetic measurements, or guessed values.

## Phase 2.12 — Inspection Assignment End-to-End Acceptance

Status: **PASS — PHASE 2 PHYSICAL-DEVICE ACCEPTANCE COMPLETE**

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
PASS — the installed Android app authenticated against the host backend and loaded assigned inspections.

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

| Check | Result | Actual observation |
|---|---|---|
| Docker/PostgreSQL/backend/web stack starts | PASS | Web, backend, PostgreSQL, and MinIO containers observed running on 2026-08-19. |
| Backend `/health` is reachable | PASS | Local backend health endpoint responded during setup. |
| Admin can log into web dashboard | PASS | Corrected seeded admin authenticated successfully; direct API login returned HTTP 200 and the admin inspection dashboard was displayed. |
| Admin can create an inspection | PASS | A fresh inspection named `Phase 2 Final Test` was manually created through the admin flow and appeared on the real Android device with its configured coordinates, radius, deadline, type, and priority. |
| Admin can assign Inspector One | PASS | `Phase 2 Final Test` appeared under Inspector One as `ASSIGNED`. |
| Physical Android device can log in as assigned inspector | PASS | Physical-device screenshots show Inspector One authenticated against the real backend. |
| Assigned inspection appears on Android | PASS | `Phase 2 Final Test` appeared on the physical Android device for Inspector One. |
| Unrelated inspector work is not visible | PASS | On the isolation-fix APK, Inspector Two showed `No inspections assigned.` after the Inspector One → sign out → Inspector Two account switch. |
| **ACKNOWLEDGE** succeeds | PASS | `Phase 2 Final Test` changed from `ASSIGNED` to `ACKNOWLEDGED` on the physical Android device and exposed `MARK READY`. |
| Web/backend persist `ACKNOWLEDGED` | PASS | The refreshed admin web dashboard showed `Phase 2 Final Test` as `ACKNOWLEDGED`. |
| **MARK READY** succeeds | PASS | `Phase 2 Final Test` reached `READY` on the physical Android device. |
| `READY` persists after refresh/restart | PASS | After fully closing and reopening SiteProof, the physical-device detail screen still showed `Phase 2 Final Test` as `READY` with `Verification ready`. |
| Assignment history is correct | PASS | Admin web detail showed `Inspector One` in `ASSIGNMENT HISTORY` as the active assignment with the recorded 2026-08-19 assignment timestamp. |
| Audit records are present and correct | PASS | Direct query against the real local PostgreSQL-backed backend returned exactly four lifecycle records for `Phase 2 Final Test`: `INSPECTION_CREATED`, `INSPECTION_ASSIGNED`, `INSPECTION_ACKNOWLEDGED`, and `INSPECTION_READY`, in chronological order. |

### Defects found and closed during acceptance

#### Seed email validation mismatch

Observed behavior:
- The original `@siteproof.local` demo addresses were rejected by the real login schema before password authentication.

Fix / retest:
- Seed identities now use or migrate to `@siteproof.example.com`.
- Reseeding succeeded against the existing PostgreSQL volume.
- Direct admin login returned HTTP 200.

#### Seed migration / duplicate employee-code collision

Observed behavior:
- After the demo email correction, an already-seeded database attempted to create duplicate inspector identities and PostgreSQL rejected duplicate employee codes such as `SP-I001`.

Fix / retest:
- The seed now migrates legacy identities in place, preserves inspector profile IDs and employee codes, refreshes passwords, and is idempotent.
- Reseeding the existing database completed successfully.

#### Android account-switch stale-list isolation defect

Observed behavior before fix:
- Inspector Two's list displayed Inspector One's prior inspection card after logout/login.
- Opening the stale card returned HTTP 404, proving server-side authorization was already blocking access.

Fix implemented:
- The authenticated Compose navigation/ViewModel graph is now scoped to the current authentication session.
- Existing persisted inspection-cache clearing remains in place.
- Android regression coverage was added.

Automated verification:
- Full CI run #283 passed backend migration/downgrade, Ruff, pytest, web tests/lint/build, Android unit tests, and debug APK assembly.
- CI run #285 built the replacement host-specific APK.

Physical retest:
- PASS — Inspector Two showed `No inspections assigned.` and no Inspector One card after the account switch.

### Final manual-flow evidence

The manually created `Phase 2 Final Test` was observed through the complete lifecycle on the real stack:

```text
ADMIN CREATE
    ↓
ASSIGNED to Inspector One
    ↓
Android ACKNOWLEDGE
    ↓
Web/backend ACKNOWLEDGED
    ↓
Android MARK READY
    ↓
READY
    ↓
Full app close/reopen
    ↓
READY persists
```

Assignment history was visible in the admin web detail view.

Direct audit query for inspection ID `bfa76c9d-898e-443a-ab96-065f37c16627` returned:

```text
2026-08-19 15:04:36.585657+00:00 INSPECTION_CREATED {}
2026-08-19 15:04:54.032812+00:00 INSPECTION_ASSIGNED {'inspectorId': 'e7d63042-b8b3-479a-9973-14da6d11a177'}
2026-08-19 15:05:57.031008+00:00 INSPECTION_ACKNOWLEDGED {}
2026-08-19 15:16:05.683707+00:00 INSPECTION_READY {}
```

### Acceptance result

Overall result:
**PASS — ALL REQUIRED PHASE 2.12 ACCEPTANCE OBSERVATIONS COMPLETED ON THE REAL LOCAL BACKEND/POSTGRESQL STACK AND PHYSICAL ANDROID DEVICE.**

Evidence recorded by:
User-observed local acceptance setup, user-provided web/Android screenshots, direct backend login result, direct PostgreSQL-backed audit query, and repository/CI verification

Test date:
2026-08-19

The physical handset model and Android version remain **NOT RECORDED**; no values are inferred or fabricated.
