# Testing

## Backend

```bash
cd backend
pytest -q
ruff check app tests alembic
```

The suite covers the Phase 2 inspection workflow plus Phase 3 verification-session creation/authorization, active-session conflicts, expiration, location-boundary handling, capture transitions, aborts, evidence initiation, independent hash checking, structural manifest/sensor/location validation, idempotent upload retry, organization isolation and authenticated evidence access.

## Migrations

CI runs PostgreSQL 16 and verifies a fresh upgrade plus Phase 3 downgrade/re-upgrade:

```bash
alembic upgrade head
alembic downgrade 0002_phase2_inspections
alembic upgrade head
```

## Web

```bash
cd web
npm install
npm test
npm run lint
npm run build
```

The admin inspection detail view polls the latest verification session, displays only evidence receipt metadata, and retrieves video through an authenticated backend endpoint. It intentionally has no authenticity/trust score.

## Android automated checks

CI uses Java 17 and Gradle 8.13:

```bash
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

Phase 3 unit tests include SHA-256 determinism/change detection, monotonic relative timestamp calculation and upload retry classification in addition to Phase 2 repository tests.

Automated Android build success proves compilation/unit behavior only. It cannot prove CameraX, sensors or GPS work on physical hardware.

## Real-device Phase 3 acceptance

**Required before Phase 3 is called complete. Do not fill PASS values unless the test was actually performed.**

### Device record

```text
Device:               NOT TESTED YET
Android version:      NOT TESTED YET
App build/commit:     NOT TESTED YET
Camera preview:       NOT TESTED YET
Video capture:        NOT TESTED YET
Accelerometer:        NOT TESTED YET
Gyroscope:            NOT TESTED YET
Rotation vector:      NOT TESTED YET
GPS freshness/radius: NOT TESTED YET
Evidence packaging:   NOT TESTED YET
Offline retention:    NOT TESTED YET
Upload/retry:         NOT TESTED YET
Admin evidence view:  NOT TESTED YET
```

### Setup

1. Put the Fedora development machine and Android phone on the same trusted LAN.
2. Start the real stack with `docker compose up --build`.
3. Seed an admin and inspector using `scripts/seed_phase2.py` and locally supplied passwords.
4. Find the Fedora LAN address with `hostname -I`.
5. Build/install Android with that address, for example:

```bash
cd android
gradle :app:assembleDebug \
  -PSITEPROOF_API_BASE_URL=http://192.168.1.20:8000/api/v1/
```

The debug manifest alone permits local cleartext HTTP; the release manifest remains HTTPS-oriented.

### Exact flow

1. Web admin creates **Verify repaired road section** at coordinates corresponding to the test location, with a realistic radius/deadline.
2. Assign the physical-device inspector.
3. Android inspector logs in, opens the assignment, taps **ACKNOWLEDGE**, then **MARK READY**.
4. Tap **START LIVE VERIFICATION**. Confirm the permission explanation appears before Android runtime permission prompts.
5. Grant camera and fine location. Confirm camera preview is from the rear camera and fresh GPS accuracy/distance is shown.
6. Confirm missing sensors, if any, are reported rather than replaced with fake values.
7. Start capture and move the phone naturally for about 15 seconds. Do not use a gallery/document picker; none should exist.
8. Stop. Confirm the app reports evidence saved/packaged and does not say Verified/Authentic/Trusted.
9. For the retry test, disable network after a completed capture before upload finishes. Confirm the app reports that evidence is safely stored locally.
10. Restore network and allow WorkManager to complete.
11. Open the inspection in the web admin dashboard. Confirm session `UPLOADED`, Video/Motion sensors/Location/Manifest received, and **Awaiting verification analysis**.
12. In development only, inspect the stored evidence object/package and confirm video is the just-recorded capture and sensor/location values are real and varying.

### Failure checks

- deny location: capture must not proceed or crash;
- stand clearly outside radius: capture start must be blocked;
- background/lock the app during active capture: session should abort rather than silently continue;
- stop before 8 seconds: UI/server must refuse completion;
- modify one evidence byte before a backend test upload: SHA-256 mismatch must be rejected;
- retry an upload: logical evidence records must not duplicate.

## Phase boundary

Do not test or claim random movement challenges, optical-flow verification, replay detection or trust scoring in Phase 3. Those are later milestones.
