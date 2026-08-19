# Testing

## Automated backend

```bash
cd backend
pytest -q
ruff check app tests alembic
```

The suite covers Phase 2 inspection management, Phase 3 live-session/evidence upload and Phase 4 active challenges. Phase 4 tests include synthetic correct rotation/tilt, wrong direction, insufficient movement, sensor disagreement, missing gyroscope, nonce failure, inspector ownership/role isolation, timestamp ordering/window attacks, idempotent duplicate submission/replay rejection, challenge expiration/replacement and a complete three-challenge API sequence.

## Migrations

GitHub CI uses PostgreSQL 16 and verifies a fresh migration plus Phase 4 downgrade/re-upgrade:

```bash
alembic upgrade head
alembic downgrade 0003_phase3_live_capture
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

The admin inspection detail shows challenge results and sensor-derived diagnostics together with Phase 3 evidence receipt status. It must not display a final authenticity/trust score.

## Android automated checks

GitHub CI uses Java 17 and Gradle 8.13:

```bash
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

Automated Android success proves compilation/unit behavior only. It cannot prove CameraX, physical sensor direction, real sample timing or user movement on hardware.

## Phase 3 physical-device acceptance

Phase 3 remains a physical-hardware prerequisite. Existing fields are deliberately not fabricated:

```text
Device:               NOT TESTED YET
Android version:      NOT TESTED YET
Camera preview:       NOT TESTED YET
Video capture:        NOT TESTED YET
Accelerometer:        NOT TESTED YET
Gyroscope:            NOT TESTED YET
Rotation vector:      NOT TESTED YET
GPS freshness/radius: NOT TESTED YET
Evidence packaging:   NOT TESTED YET
Upload/retry:         NOT TESTED YET
Admin evidence view:  NOT TESTED YET
```

## Phase 4 physical-device acceptance

**Phase 4 must not be called complete until this section is replaced with actual observations from at least one Android phone.**

### Device record

```text
Device model:              NOT TESTED YET
Android version:           NOT TESTED YET
App commit/build:          NOT TESTED YET
Gyroscope available:       NOT TESTED YET
Rotation vector available: NOT TESTED YET
Observed gyro sample rate: NOT TESTED YET
Observed max sensor gap:   NOT TESTED YET
Rear CameraX continuity:   NOT TESTED YET
```

### Setup

1. Put the Fedora development machine and Android phone on the same trusted LAN.
2. Check out `phase4/challenge-engine`.
3. Start the stack with `docker compose up --build`.
4. Seed admin/inspector accounts using locally chosen passwords.
5. Get the Fedora LAN address with `hostname -I`.
6. Build/install Android with that address, for example:

```bash
cd android
gradle :app:assembleDebug \
  -PSITEPROOF_API_BASE_URL=http://192.168.1.20:8000/api/v1/
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The release app remains HTTPS-oriented; local debug networking is for development testing only.

### Required end-to-end flow

1. Admin creates an inspection at the actual test location with a realistic radius/deadline and assigns the physical-device inspector.
2. Android inspector logs in, taps **ACKNOWLEDGE**, then **MARK READY**.
3. Tap **START LIVE VERIFICATION** and confirm the rear camera begins one continuous recording.
4. Confirm Challenge #1 arrives from the server only after capture begins. Record its type/target.
5. Perform the requested motion naturally. Confirm the backend returns `PASS`, `FAIL` or `INCONCLUSIVE` and the Android UI does not show raw security thresholds.
6. Confirm Challenge #2 is not known before Challenge #1 finishes, then perform it.
7. Repeat for Challenge #3.
8. Confirm the camera never restarts between challenges.
9. Confirm capture finalizes only after the required challenge sequence is terminal.
10. Confirm video, full sensor package, location, metadata and manifest upload through the Phase 3 pipeline.
11. In admin web, confirm the challenge timeline/result/score and Video/Sensors/Location/Manifest status are visible, while **Final authenticity: Not yet calculated** remains visible.

### Legitimate-movement trials

Perform each challenge at least 10 times when practical and record real counts only:

```text
ROTATE_RIGHT:  PASS __/10 | INCONCLUSIVE __/10 | FAIL __/10
ROTATE_LEFT:   PASS __/10 | INCONCLUSIVE __/10 | FAIL __/10
TILT_UP:       PASS __/10 | INCONCLUSIVE __/10 | FAIL __/10
TILT_DOWN:     PASS __/10 | INCONCLUSIVE __/10 | FAIL __/10
```

Current state:

```text
ROTATE_RIGHT: NOT TESTED YET
ROTATE_LEFT:  NOT TESTED YET
TILT_UP:      NOT TESTED YET
TILT_DOWN:    NOT TESTED YET
```

Tune `ROTATION_RIGHT_SIGN`, `TILT_DOWN_SIGN`, sensor thresholds and tolerances only from observed real-device behavior.

### Deliberately wrong-motion trials

Record actual observations:

```text
Requested ROTATE_RIGHT, performed ROTATE_LEFT: NOT TESTED YET
Requested ROTATE_LEFT, performed ROTATE_RIGHT: NOT TESTED YET
Requested TILT_DOWN, stayed still:              NOT TESTED YET
Requested TILT_UP, random shake:                NOT TESTED YET
```

Clearly wrong movements should usually fail; noisy/insufficient evidence may be inconclusive where appropriate.

### Nonce/timestamp/network checks

Automated tests cover structural attacks. On-device additionally verify:

- let a challenge expire; stale continuation must not be accepted;
- briefly disconnect after current challenge starts; current evidence is preserved and future challenge is not preloaded;
- reconnect and retry the same saved submission without creating a duplicate result;
- background or lock the phone during an active challenge; session should abort rather than silently continue;
- confirm one continuous video still covers all completed challenge intervals.

### Admin verification record

```text
Challenge timeline visible:                 NOT TESTED YET
PASS/FAIL/INCONCLUSIVE visible:             NOT TESTED YET
Sensor-derived metrics visible to admin:    NOT TESTED YET
Final authenticity absent/not calculated:   NOT TESTED YET
```

## Security boundary test

Even after a real sensor challenge passes, Phase 4 must **not** claim the visible scene is genuine. A phone can theoretically be rotated correctly while its camera points at prerecorded content. Phase 5 will compare challenge-time video motion with the synchronized sensor timeline.

## Phase 5 readiness check

After real-device Phase 4 testing, confirm with actual evidence that these are synchronized:

```text
continuous video:       NOT TESTED YET
challenge relative time: NOT TESTED YET
sensor relative time:    NOT TESTED YET
```

Do not replace `NOT TESTED YET` with guessed measurements.
