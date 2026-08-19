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
NOT RECORDED

Phone and host on same network:
NOT RECORDED

Backend health before test:
NOT RECORDED

PostgreSQL/Docker stack status:
NOT RECORDED

### Setup

1. Copy the environment template and set local secrets:

```bash
cp .env.example .env
```

2. Start the real local stack:

```bash
docker compose up --build
```

3. Seed Phase 2 development accounts using local passwords:

```bash
export SITEPROOF_DEMO_ADMIN_PASSWORD='choose-a-local-password'
export SITEPROOF_DEMO_INSPECTOR_PASSWORD='choose-another-password'
cd backend
python ../scripts/seed_phase2.py
```

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
| Docker/PostgreSQL/backend/web stack starts | NOT TESTED | |
| Backend `/health` is reachable | NOT TESTED | |
| Admin can log into web dashboard | NOT TESTED | |
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
NOT RECORDED

Evidence recorded by:
NOT RECORDED

Test date/time:
NOT RECORDED

### Rule for closing Phase 2.12

Only change the overall result to PASS after the complete physical-device flow has been run against the real backend/PostgreSQL stack and every required observation above has been recorded. If any required step fails, keep the milestone open, record the exact failure, fix it, rerun the relevant tests, and repeat the device flow.
