# Testing

## Automated backend

```bash
cd backend
pytest -q
ruff check app tests alembic
```

The suite covers Phase 2 inspection management, Phase 3 live-session/evidence upload and Phase 4 active challenges. Phase 4 tests include synthetic correct rotation/tilt, wrong direction, insufficient movement, sensor disagreement, missing gyroscope, nonce failure, inspector ownership/role isolation, timestamp ordering/window attacks, idempotent duplicate submission/replay rejection, challenge expiration/replacement, retry-budget behavior and a complete three-challenge API sequence.

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

The Phase 4 UX acceptance also verifies that inspection creation/editing supports location search, search-result map recentering, coordinate filling, and browser **Use current location**, while click-on-map/manual coordinates remain available.

## Android automated checks

GitHub CI uses Java 17 and Gradle 8.13:

```bash
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

Automated Android success proves compilation/unit behavior only. CameraX, physical sensor direction, real sample timing and user movement require hardware testing.

## Phase 3 physical-device acceptance

**PASS — completed on 2026-08-19.**

Observed on a physical Android phone:

```text
Physical Android device: PASS (model not recorded)
Android version:         NOT RECORDED
Camera preview:          PASS
Video capture:           PASS
Accelerometer:           PASS
Gyroscope:               PASS
Rotation vector:         PASS
GPS freshness/radius:    PASS
Evidence packaging:      PASS
Upload/retry:            PASS
Admin evidence view:     PASS
Network-loss recovery:   PASS
```

The test produced real CameraX video, motion sensors and location data, packaged them with the manifest, uploaded them to the backend, displayed them in admin, and recovered after temporary network loss.

## Phase 4 physical-device acceptance

**PASS — completed on 2026-08-20 on a physical Android phone.**

### Device record

```text
Device model:              Physical Android phone; exact model NOT RECORDED
Android version:           NOT RECORDED
Android UX APK baseline:   Phase 4 UX build from f4ee7b3a32f735e7421efe87ad2031b5e5dad759
Backend retry baseline:    66494bd05723b2dc621404c8b85c0ad053fa3a32
Gyroscope available:       PASS
Rotation vector available: PASS
Observed gyro sample rate: NOT FORMALLY MEASURED
Observed max sensor gap:   NOT FORMALLY MEASURED
Rear CameraX continuity:   PASS
```

Exact device model/version and formal sample-rate/gap statistics were not recorded during the manual session and are deliberately not invented.

### Required end-to-end flow — observed

1. Admin inspection at the real test location: **PASS**.
2. Inspector login, ACKNOWLEDGE and MARK READY: **PASS**.
3. START LIVE VERIFICATION with rear CameraX continuous capture: **PASS**.
4. Server issues Challenge #1 only after capture begins: **PASS**.
5. Real requested movement produces PASS / FAIL / INCONCLUSIVE and human-readable guidance instead of requiring exact-degree estimation: **PASS**.
6. Challenge #2 is issued after the previous challenge terminates: **PASS**.
7. Challenge #3 completes the required sequence: **PASS**.
8. Camera remains continuous across the challenge sequence: **PASS**.
9. Capture finalizes after the challenge sequence reaches a terminal state: **PASS**.
10. Video, full sensor package, location, metadata and manifest upload through the Phase 3 pipeline: **PASS**.
11. Admin challenge timeline/result/score plus Video/Sensors/Location/Manifest receipt status are visible while final authenticity remains not calculated: **PASS**.

### Real observed challenge sessions

Multiple physical runs were performed. One successful run recorded:

```text
Challenge 1: ROTATE_LEFT  — PASS 96%
Challenge 2: TILT_DOWN    — PASS 85%
Challenge 3: TILT_UP      — PASS 93%
Final: 3 Pass · 0 Fail · 0 Inconclusive
Capture duration: 19 s
Accelerometer samples: 1487
Gyroscope samples: 966
Rotation-vector samples: 964
Location samples: 18
Video / Motion sensors / Location / Manifest: all Received
```

A later run exercised retry behavior:

```text
Challenge 1: ROTATE_RIGHT — PASS 84%
Challenge 2 attempt 1: ROTATE_LEFT — INCONCLUSIVE
Challenge 2 attempt 2: ROTATE_RIGHT — PASS 84%
Challenge 3: TILT_DOWN — PASS 97%
Final: 3 Pass · 0 Fail · 0 Inconclusive
Capture duration: 18 s
Accelerometer samples: 1428
Gyroscope samples: 890
Rotation-vector samples: 887
Location samples: 13
Video / Motion sensors / Location / Manifest: all Received
```

These are real observed session values, not synthetic CI values.

### Challenge directions / UX

Physical testing confirmed the user-facing movement guide works for all four challenge families:

```text
ROTATE_RIGHT: PASS observed
ROTATE_LEFT:  PASS observed
TILT_UP:      PASS observed
TILT_DOWN:    PASS observed
```

The Android UI shows an animated phone/directional arrow, human-readable movement copy, and live progress states so the inspector does not need to estimate an exact target degree manually.

A formal 10-trial statistical pass/inconclusive/fail table for every motion family was **not** recorded during this acceptance session. Do not infer percentages beyond the observed runs above.

### Retry behavior

**PASS.** Manual hardware testing confirmed:

```text
Initial attempt + at least 3 explicit reattempts: PASS
Retry after FAIL / INCONCLUSIVE:                PASS
Fresh challenge ID/nonce/evidence window:       PASS by implementation + observed fresh challenge flow
Retry budget is per challenge sequence:         PASS
Fourth total attempt available:                 PASS
Verification retry:                             PASS
Upload retry / Phase 3 recovery:                PASS
```

The backend guarantees a minimum `CHALLENGE_MAX_RETRIES=3`, and retry accounting is per challenge sequence so an earlier challenge's retries do not consume the next challenge's allowance.

### Map/location UX

```text
Location search:                 PASS
Search result recenters map:     PASS
Latitude/longitude auto-fill:    PASS
Use current location:            PASS
Click-on-map fallback retained:  PASS
Manual coordinates retained:     PASS
```

### Deliberately wrong / inconclusive behavior

Manual testing intentionally produced failed/inconclusive attempts in order to exercise retry behavior, and the app/server did not silently reuse stale evidence. A systematic wrong-motion matrix (e.g. 10 wrong-direction trials for each movement family) was not recorded, so no rejection-rate percentage is claimed.

### Nonce/timestamp/network checks

Automated tests cover structural timestamp, nonce, replay and idempotency attacks. Physical-device testing additionally confirmed:

- fresh challenge issuance on retry rather than stale evidence reuse: **PASS**;
- temporary network-loss recovery from the Phase 3 upload pipeline: **PASS**;
- explicit retry actions for challenge, verification and upload flows: **PASS**;
- one continuous evidence package reaches admin with challenge timing plus sensor/location data: **PASS**.

A dedicated measured stale-expiry timing study and formal background/lock matrix were not recorded in this acceptance session and should remain separate hardening tests if required before production deployment.

### Admin verification record

```text
Challenge timeline visible:                 PASS
PASS/FAIL/INCONCLUSIVE visible:             PASS
Sensor-derived metrics visible to admin:    PASS
Video received:                             PASS
Motion sensors received:                    PASS
Location received:                          PASS
Manifest received:                          PASS
Final authenticity absent/not calculated:   PASS
```

## Security boundary test

Even after a real sensor challenge passes, Phase 4 does **not** claim the visible scene is genuine. A phone can theoretically move correctly while its camera points at prerecorded content. Phase 5 will compare challenge-time video motion with the synchronized sensor timeline.

## Phase 5 readiness check

Phase 4 now provides the required inputs for Phase 5:

```text
continuous video:        PRESENT / physically verified
challenge relative time: PRESENT in evidence metadata/timeline
sensor relative time:    PRESENT in common monotonic timeline
```

**Phase 5 may now begin.** Its acceptance must verify visual camera motion against these synchronized challenge/sensor intervals; Phase 4 sensor validation remains intact and authoritative for the phone-motion portion.
