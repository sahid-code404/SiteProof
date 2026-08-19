# SiteProof Device Testing

This document records **actual physical-device results only**. Never replace missing hardware evidence with emulator assumptions, synthetic measurements, or guessed values.

## Phase 2.12 — Inspection Assignment End-to-End Acceptance

Status: **NOT TESTED YET**

### Device / environment

Device:
NOT RECORDED

Android version:
NOT RECORDED

SiteProof APK/build:
NOT RECORDED

Host machine LAN IP:
192.168.1.102 — observed during the 2026-08-19 acceptance setup

Phone and host on same network:
NOT RECORDED

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
| Admin can log into web dashboard | NOT TESTED | Initial attempt exposed the invalid `.local` seed-email defect; fix committed, retest pending. |
| Admin can create an inspection | NOT TESTED | |
| Admin can assign Inspector One | NOT TESTED | |
| Physical Android device can log in as assigned inspector | NOT TESTED | |
| Assigned inspection appears on Android | NOT TESTED | |
| Unrelated inspector work is not visible | NOT TESTED | |
| **ACKNOWLEDGE** succeeds | NOT TESTED | |
| Web/backend persist `ACKNOWLEDGED` | NOT TESTED | |
| **MARK READY** succeeds | NOT TESTED | |
| `READY` persists after refresh/restart | NOT TESTED | |
| Assignment history is correct | NOT TESTED | |
| Audit records are present and correct | NOT TESTED | |

### Acceptance result

Overall result:
**NOT TESTED YET**

Blocking defect(s):
- RESOLVED IN CODE, RETEST PENDING — Phase 2 seed accounts previously used `@siteproof.local`; the login `EmailStr` schema rejects that special-use domain with HTTP 422. Seed addresses now use `@siteproof.example.com`, with an automated contract test preventing recurrence.

Evidence recorded by:
User-observed local acceptance setup plus repository/CI verification

Test date/time:
2026-08-19

### Rule for closing Phase 2.12

Only change the overall result to PASS after the complete physical-device flow has been run against the real backend/PostgreSQL stack and every required observation above has been recorded. If any required step fails, keep the milestone open, record the exact failure, fix it, rerun the relevant tests, and repeat the device flow.
