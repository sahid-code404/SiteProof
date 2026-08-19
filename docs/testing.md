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

**Phase 4 must not be called accepted until this section is replaced with actual observations from at least one Android phone.**

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

1. Put the development machine and Android phone on the same trusted LAN.
2. Check out the phase branch under test.
3. Start the stack with `docker compose up --build`.
4. Seed admin/inspector accounts using locally chosen passwords.
5. Get the development machine LAN address with `hostname -I`.
6. Build/install Android with that address, for example:

```bash
cd android
gradle :app:assembleDebug \
  -PSITEPROOF_API_BASE_URL=http://192.168.1.20:8000/api/v1/
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The release app remains HTTPS-oriented; local debug networking is for development testing only.

### Required Phase 4 end-to-end flow

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

### Phase 4 legitimate-movement trials

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

Tune Phase 4 sensor signs/thresholds only from observed real-device behavior.

### Deliberately wrong-motion trials

```text
Requested ROTATE_RIGHT, performed ROTATE_LEFT: NOT TESTED YET
Requested ROTATE_LEFT, performed ROTATE_RIGHT: NOT TESTED YET
Requested TILT_DOWN, stayed still:              NOT TESTED YET
Requested TILT_UP, random shake:                NOT TESTED YET
```

### Nonce/timestamp/network checks

On-device verify:

- expired challenge cannot continue;
- disconnect after current challenge starts preserves current evidence without preloading future challenges;
- reconnect retry does not create duplicate challenge results;
- background/lock during active challenge aborts the live session;
- one continuous video covers all completed challenge intervals.

### Phase 4 admin verification record

```text
Challenge timeline visible:                 NOT TESTED YET
PASS/FAIL/INCONCLUSIVE visible:             NOT TESTED YET
Sensor-derived metrics visible to admin:    NOT TESTED YET
Final authenticity absent/not calculated:   NOT TESTED YET
```

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
