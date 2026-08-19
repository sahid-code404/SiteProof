# Project State

Current development branch: **Phase 5 — Visual Motion Analysis & Camera Movement Estimation**

Working branch: `phase5-visual-motion`

Base branch: `phase4/challenge-engine`

Draft PR: **#4 — Phase 5: visual motion analysis and camera movement estimation**

Phase 5 is intentionally stacked on Phase 4. Previous capture/challenge functionality is extended rather than rebuilt.

## Existing Phase 4 foundation

Phase 4 provides:

- one continuous CameraX recording across the complete challenge sequence;
- accelerometer, gyroscope, rotation-vector and location evidence;
- one common Android monotonic capture anchor;
- unpredictable ROTATE_LEFT, ROTATE_RIGHT, TILT_UP and TILT_DOWN challenges;
- per-challenge issued/start/completion timestamps relative to the common capture timeline;
- server-side sensor validation and PASS / FAIL / INCONCLUSIVE challenge results;
- SHA-256 evidence/manifest verification and storage abstraction;
- admin/reviewer sensor challenge timeline.

Phase 4 real-device acceptance remains a prerequisite and must not be replaced by CI results.

## Phase 5 implemented in code

The Phase 5 branch currently includes:

- OpenCV, NumPy and SciPy backend dependencies;
- independent server-side video metadata inspection;
- challenge-to-video timeline mapping using `videoStartRelativeNs` and challenge relative timestamps;
- configurable challenge-window padding, analysis FPS and down-scaled working resolution;
- ORB visual feature-quality measurement;
- grid-distributed Shi-Tomasi tracking points;
- Lucas-Kanade sparse optical flow with forward/backward filtering;
- RANSAC partial-affine global motion estimation;
- optional homography support as a secondary diagnostic;
- physical camera LEFT/RIGHT and UP/DOWN direction semantics separated from image-content motion;
- approximate visual movement magnitude;
- per-frame-pair motion energy and visual movement start/end timing;
- configurable visual confidence from feature quality, inlier ratio, consistency, coverage and continuity;
- scene-cut, duplicate/frozen-frame, black-frame, brightness and sharpness metrics;
- `visual_motion_results` persistence keyed by challenge + algorithm version;
- FastAPI background analysis after verified evidence upload;
- secure temporary video materialization for local/S3-compatible evidence storage;
- ADMIN/REVIEWER visual-analysis API and retry endpoint;
- reviewer dashboard visual-only evidence panel;
- visual-analysis audit events;
- deterministic synthetic CV tests;
- `docs/visual-motion-analysis.md`.

## Phase boundary

Phase 5 produces **visual-motion evidence only**.

It does **not** calculate:

- gyroscope-vs-video agreement;
- visual-inertial consistency;
- final replay-risk classification;
- overall SiteProof trust score;
- VERIFIED / FLAGGED / AUTHENTIC verdicts;
- anomaly-detection ML.

Those belong to Phase 6 and later.

## Automated validation status

The first Phase 5 CI run installed the new CV dependencies, passed fresh/downgrade/re-upgrade migrations, passed Ruff, passed all web checks, and passed the new CV tests. It exposed one existing Phase 3 upload lifecycle regression: an expected durable `UPLOADED` session could remain transiently `PROCESSING` when background visual analysis failed on legacy metadata without a challenge timeline.

That lifecycle issue has been corrected on the branch. The latest CI result after the correction remains the source of truth; do not describe Phase 5 automated validation as green until that run completes successfully.

## Real-video acceptance status

**NOT TESTED YET / NOT ACCEPTED YET.**

Phase 5 must not be called complete until video recorded by the actual SiteProof Android application is uploaded and the backend produces defensible visual-motion results for real challenges.

Required real-world observations still include:

- real `capture.mp4` decoding through the evidence pipeline;
- actual challenge/video timestamp alignment;
- real ROTATE_RIGHT / ROTATE_LEFT / TILT_UP / TILT_DOWN direction results;
- SUCCESS / INCONCLUSIVE / wrong-direction rates;
- low-light and motion-blur behavior;
- scene continuity/freeze behavior on real captures;
- actual processing duration and memory observations where practical;
- reviewer dashboard end-to-end display.

No real-device/video measurements are to be fabricated.

## Phase 6 readiness condition

Phase 6 may start only after real Phase 5 acceptance. At that point each challenge must have two independent measurements on the same synchronized timeline:

```text
Phase 4: sensor-derived physical movement
Phase 5: visual-derived camera/scene movement
```

Phase 5 itself does not compare them.

## Source of truth

1. `docs/project-spec.md`
2. `docs/challenge-engine.md`
3. `docs/visual-motion-analysis.md`
4. `docs/live-capture.md`
5. `docs/session-lifecycle.md`
6. `docs/api.md`
7. `docs/testing.md`
8. current repository code and actual CI/device/video results
