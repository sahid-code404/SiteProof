# Testing

## Automated backend

```bash
cd backend
pytest -q
ruff check app tests alembic
```

The suite covers Phase 2 inspection management, Phase 3 live-session/evidence upload, Phase 4 active challenges, and Phase 5 deterministic computer vision.

Phase 4 coverage includes correct rotation/tilt, wrong direction, insufficient movement, sensor disagreement, missing gyroscope, nonce failure, inspector ownership/role isolation, timestamp ordering/window attacks, idempotent duplicate submission/replay rejection, challenge expiration/replacement and a complete three-challenge API sequence.

Phase 5 deterministic coverage includes:

- challenge/session/video timeline mapping;
- horizontal physical-camera direction from opposite scene translation;
- vertical tilt direction;
- synthetic affine image rotation;
- low-feature `INCONCLUSIVE` behavior;
- RANSAC rejection of independently moving outliers;
- scene-cut detection;
- duplicate/frozen-frame measurement;
- corrupted media failure;
- video metadata inspection;
- sampled-frame timestamp retention.

Synthetic CV tests prove implementation behavior; they do **not** prove real phone-camera accuracy.

## Migrations

GitHub CI uses PostgreSQL 16 and verifies a fresh migration plus the latest phase downgrade/re-upgrade:

```bash
alembic upgrade head
alembic downgrade 0004_phase4_challenges
alembic upgrade head
```

The current head after Phase 5 migration must be `0005_phase5_visual_motion`.

## Web

```bash
cd web
npm install
npm test
npm run lint
npm run build
```

The reviewer inspection detail must show separate sensor and camera evidence sections. It must not display sensor-camera consistency or a final authenticity/trust score.

## Android automated checks

GitHub CI uses Java 17 and Gradle 8.13:

```bash
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

Automated Android success proves compilation/unit behavior only. It cannot prove CameraX, physical sensor direction, real sample timing, video quality or visual-analysis accuracy on hardware.

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
## Phase 5 automated CV interpretation

Phase 5 automated tests must remain deterministic and independent from Phase 4 sensor results. A test may synthesize image transforms and assert the camera-side direction/magnitude, but it must not calculate a gyro/video agreement score.

For direction semantics:

```text
physical camera yaw RIGHT → static scene usually moves LEFT in image X
physical camera yaw LEFT  → static scene usually moves RIGHT in image X
```

For tilt, vertical scene motion is used only as an approximate monocular pitch signal.

Low-feature, corrupt or poorly supported transforms must return `INCONCLUSIVE`/`FAILED` according to the documented distinction rather than fake a reliable visual estimate.

## Phase 5 real-video acceptance

**Phase 5 is NOT ACCEPTED until actual video recorded by the SiteProof Android application is processed by the backend.**

Current state:

```text
Real SiteProof capture.mp4 decoded:        NOT TESTED YET
Video/challenge timeline alignment:        NOT TESTED YET
ROTATE_RIGHT visual direction:             NOT TESTED YET
ROTATE_LEFT visual direction:              NOT TESTED YET
TILT_UP visual direction:                  NOT TESTED YET
TILT_DOWN visual direction:                NOT TESTED YET
Low-light behavior:                        NOT TESTED YET
Motion-blur behavior:                      NOT TESTED YET
Textureless-scene behavior:                NOT TESTED YET
Scene-cut metrics on real video:           NOT TESTED YET
Duplicate/freeze metrics on real video:    NOT TESTED YET
Reviewer visual-analysis panel:            NOT TESTED YET
Actual processing duration:                NOT TESTED YET
Peak memory if practical:                  NOT TESTED YET
```

### Required Phase 5 capture workflow

For every test session:

1. Record through the real SiteProof Android live-verification flow; do not import a gallery video.
2. Keep one continuous CameraX recording across all server challenges.
3. Complete upload normally so video, metadata and manifest pass the existing SHA-256 checks.
4. Confirm the backend independently decodes codec, width, height, FPS, duration and frame count.
5. Confirm `videoStartRelativeNs` and challenge relative timestamps map each challenge to the expected video interval.
6. Inspect the resulting visual status, direction, approximate magnitude, confidence, tracked features, RANSAC inliers and continuity metrics.
7. Confirm the reviewer web panel shows **CAMERA EVIDENCE** separately from Phase 4 **SENSOR EVIDENCE**.
8. Confirm no sensor-camera consistency percentage or final authenticity verdict is displayed.

### Required real-world validation counts

Target the Phase 5 specification's practical minimum and record actual results only:

```text
ROTATE_RIGHT: 10 legitimate captures
ROTATE_LEFT:  10 legitimate captures
TILT_UP:       5 legitimate captures
TILT_DOWN:     5 legitimate captures
```

Record results in this format after testing:

```text
ROTATE_RIGHT
sessions tested: __
SUCCESS:         __
INCONCLUSIVE:    __
WRONG DIRECTION: __

ROTATE_LEFT
sessions tested: __
SUCCESS:         __
INCONCLUSIVE:    __
WRONG DIRECTION: __

TILT_UP
sessions tested: __
SUCCESS:         __
INCONCLUSIVE:    __
WRONG DIRECTION: __

TILT_DOWN
sessions tested: __
SUCCESS:         __
INCONCLUSIVE:    __
WRONG DIRECTION: __
```

Current measured results:

```text
ROTATE_RIGHT: NOT TESTED YET
ROTATE_LEFT:  NOT TESTED YET
TILT_UP:      NOT TESTED YET
TILT_DOWN:    NOT TESTED YET
```

### Real-scene variety

Use several backgrounds rather than one repeated room:

```text
room:              NOT TESTED YET
road:              NOT TESTED YET
corridor:          NOT TESTED YET
building exterior: NOT TESTED YET
vegetation:        NOT TESTED YET
```

This is evaluation data, not a training dataset.

### Poor-video demonstration

Record at least one legitimate but visually difficult case such as:

```text
camera mostly covered / very dark / heavily blurred / textureless wall
```

Expected behavior is not a forced direction. The backend should return a defensible `INCONCLUSIVE` or technical `FAILED` result with an explainable reason.

Actual poor-video observation:

```text
NOT TESTED YET
```

### Phase 5 processing performance

For real SiteProof evidence measure where practical:

```text
15 sec / 1080p input processing time: NOT TESTED YET
30 sec / 1080p input processing time: NOT TESTED YET
15 sec / 720p input processing time:  NOT TESTED YET
30 sec / 720p input processing time:  NOT TESTED YET
sampled frame count:                   NOT TESTED YET
peak memory:                           NOT TESTED YET
```

Do not infer these values from synthetic unit tests.

### Phase 5 limitations to observe

Record whether real failures correlate with:

- low light;
- motion blur;
- textureless scenes;
- independently moving foreground objects;
- autofocus scale changes;
- rolling-shutter distortion;
- approximate monocular rotation/FOV assumptions.

Do not tune thresholds to manufacture desired pass rates. Tune only from measured evidence and keep uncertain cases inconclusive.

## Security boundary test

Even when visual analysis returns `SUCCESS`, Phase 5 does **not** prove authenticity. Camera motion may look plausible while physical phone sensors disagree, and physical sensors may look plausible while the scene motion is inconsistent.

That comparison is intentionally deferred to Phase 6.

## Phase 6 readiness check

Do not replace these values until real Phase 4 + Phase 5 evidence has been observed:

```text
continuous video spans all challenges:       NOT TESTED YET
challenge relative timeline confirmed:       NOT TESTED YET
sensor relative timeline confirmed:          NOT TESTED YET
visual relative timeline confirmed:          NOT TESTED YET
sensor-derived result per challenge exists:  NOT TESTED YET
visual-derived result per challenge exists:  NOT TESTED YET
```

Only after these are confirmed may Phase 6 compare camera and sensor evidence.
