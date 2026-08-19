# Phase 5 Visual Motion Analysis

## Purpose and phase boundary

Phase 5 independently measures how the visible camera scene moved during each active challenge in the continuous SiteProof video. It produces **camera-side visual evidence only**.

It does not compare visual motion with gyroscope or rotation-vector evidence, and it does not produce a final authenticity, replay-risk, VERIFIED, or FLAGGED verdict. That cross-signal comparison belongs to Phase 6.

## Existing capture timeline

Phase 3/4 already provide one common Android monotonic capture anchor:

```text
captureStartNs = SystemClock.elapsedRealtimeNanos()
```

The evidence metadata stores:

```text
capture.videoStartRelativeNs
challenge.issuedRelativeMs
challenge.startedRelativeMs
challenge.completedRelativeMs
```

All are relative to the same capture anchor. Therefore Phase 5 maps a challenge session timestamp to video time as:

```text
videoTimeMs = challengeSessionRelativeMs - videoStartRelativeMs
```

The analyzer expands each challenge window with configurable pre/post padding so baseline, motion and settling are available. The default is 500 ms before and 500 ms after.

The backend also cross-checks the challenge's server-stored `client_start_monotonic_ns` against the client evidence timeline. A large mismatch fails analysis instead of silently inspecting the wrong video interval.

## Video handling and security

Uploaded video is untrusted input. Phase 5:

- analyzes only evidence records that were uploaded and SHA-256 verified by the existing evidence pipeline;
- retrieves objects with internal storage credentials rather than creating permanent public URLs;
- validates storage keys through the existing storage service;
- materializes S3-compatible objects into a secure temporary directory when necessary;
- removes temporary files when processing ends;
- rejects videos outside configured duration, resolution and frame-count limits;
- treats decoder failures as processing failures rather than crashing the API process.

The original uploaded video remains unchanged. OpenCV analyzes derived, down-scaled frames only.

## Video metadata

`video_reader.py` uses OpenCV to independently inspect:

```text
codec
width
height
fps
duration
frame count
```

Decoded duration is compared with Android's capture duration using a configurable tolerance. Width, height, FPS and frame count are derived server-side rather than trusted from the client.

The default analysis rate is 12 FPS and the derived working image is at most 960 pixels wide.

## Frame model

Every sampled frame preserves both clocks:

```text
VisualFrame(
    frame_index=...,
    video_time_ms=...,
    session_time_ms=...,
    image=...
)
```

This timing metadata is retained through the pipeline because Phase 6 will later align visual motion with physical sensor motion.

## Preprocessing

Preprocessing is intentionally conservative:

1. resize while preserving aspect ratio;
2. convert to grayscale;
3. measure brightness;
4. measure sharpness using variance of the Laplacian.

No aggressive denoising or enhancement is applied because it could remove real trackable features.

## Feature detection and spatial coverage

Two classical OpenCV feature methods are used for different purposes:

- ORB gives an explainable feature-count quality signal;
- Shi-Tomasi corners provide stable points for sparse optical flow.

Tracking points are selected across a configurable 4×4 image grid. This reduces the risk of estimating global motion from one small textured region while the rest of the scene is unsupported.

Low-texture scenes are not forced into a movement result. If there are too few stable visual features the challenge returns `INCONCLUSIVE`.

## Sparse optical flow

For a feature location `p_t` in frame `t`, Lucas-Kanade estimates its location `p_(t+1)` in the next frame.

```text
v = p_(t+1) - p_t
```

SiteProof uses `cv2.calcOpticalFlowPyrLK` and filters tracks with:

- OpenCV status flags;
- finite-value checks;
- forward-backward tracking consistency;
- image-bound checks;
- implausibly large displacement rejection.

Forward-backward consistency tracks the point A→B and then B→A. If it does not return close to the original location, the track is rejected.

## RANSAC global motion

Cars, people, vegetation and other foreground objects can move independently of the camera. SiteProof therefore does not average every optical-flow vector.

For each consecutive sampled-frame pair, it estimates a global partial affine transform using:

```text
cv2.estimateAffinePartial2D(..., method=cv2.RANSAC)
```

Conceptually, RANSAC repeatedly tests candidate transforms and keeps the transform supported by the largest consistent subset of feature tracks. Features that do not support the dominant scene motion become outliers.

When enough correspondences exist, `cv2.findHomography(..., RANSAC)` is also calculated as a secondary diagnostic. Homography is not assumed to be valid for every scene.

## Affine transformation and rotation

A 2D partial affine transformation can be written as:

```text
[x']   [a -b][x]   [tx]
[y'] = [b  a][y] + [ty]
```

`tx` and `ty` represent image translation. The approximate image-plane rotation is:

```text
θ = atan2(b, a)
```

The analyzer stores per-frame-pair rotation, translation, scale, tracked-point count, inlier count, inlier ratio, feature coverage and optional homography support.

## Camera movement direction

Image-content direction and physical-camera direction are not the same.

For Phase 4 portrait left/right challenges, the primary visual model is camera yaw. A camera yaw to the right generally makes a static scene move left in image coordinates. Therefore the horizontal scene translation is inverted before returning physical camera `RIGHT`/`LEFT` semantics.

For tilt challenges, vertical image translation gives an approximate pitch direction. The result is intentionally approximate because a monocular camera cannot recover precise physical pitch for arbitrary 3D scenes without additional assumptions.

For synthetic or unusual motion where image-plane affine rotation clearly dominates translation, a labelled affine-rotation fallback is retained. Diagnostics state which signal produced the direction so it cannot be silently confused with the normal yaw model.

## Approximate magnitude

For the primary translation model, a rough angular displacement is estimated using an assumed horizontal field of view:

```text
f_px = (imageWidth / 2) / tan(HFOV / 2)
angle ≈ atan2(sceneTranslationPx, f_px)
```

The default HFOV is a configurable prototype assumption. This is a useful approximate visual magnitude, not camera calibration ground truth.

Frame-pair estimates are accumulated across the challenge. A direct start/end affine estimate is also attempted as a diagnostic cross-check when tracking remains stable.

## Visual confidence

The visual confidence score is independent from the Phase 4 sensor score. Default normalized components are:

```text
feature quality      0.20
RANSAC inlier ratio  0.30
motion consistency   0.25
spatial coverage     0.15
frame continuity     0.10
```

A high confidence means the visual-motion measurement is well supported. It does **not** mean the SiteProof submission is authentic.

Statuses are:

```text
PENDING
PROCESSING
SUCCESS
INCONCLUSIVE
FAILED
```

`SUCCESS` means visual movement could be analyzed. `INCONCLUSIVE` means valid media did not provide enough reliable visual information. `FAILED` means a technical/structural processing failure.

## Motion energy and timing

Each RANSAC-supported frame pair stores median optical-flow magnitude. This creates an explainable motion curve:

```text
time → median flow magnitude
```

The first and last frame pairs above the configurable movement threshold become approximate `motion_start_ms` and `motion_end_ms`. These remain on the common session timeline for Phase 6.

## Scene continuity

Phase 5 measures continuity without making a final replay verdict.

Adjacent frames are checked for:

- mean absolute pixel difference;
- grayscale histogram distance;
- duplicate frames;
- longest freeze interval;
- black-frame ratio;
- invalid/decode ratio;
- mean brightness;
- mean sharpness.

An abrupt histogram change can set `sceneCutDetected=true`. Repeated frames contribute to `duplicateFrameRatio` and `freezeDurationMs`. These are supporting observations, not automatic claims of malicious behavior.

## Persistence and idempotency

`visual_motion_results` stores one result per:

```text
challenge_id + analysis_version
```

The initial version is `vision-v1.0`. Re-running the same version updates the existing versioned result instead of creating conflicting duplicate rows. Future algorithm versions can coexist without silently changing the meaning of older reports.

Important columns include direction, approximate rotation, translation, scale, motion timing, feature counts, inlier ratio, confidence, continuity, duplicate/freeze metrics and analysis version. Variable diagnostic details live in JSON.

## Background processing

After all evidence is successfully uploaded and the manifest is verified:

```text
UPLOADED
   ↓
FastAPI background task
   ↓
PROCESSING
   ↓
video metadata + timeline validation
   ↓
per-challenge OpenCV analysis
   ↓
visual_motion_results
```

FastAPI `BackgroundTasks` is intentionally used for the prototype because the repository did not already contain Redis/Celery/RQ infrastructure. This avoids adding infrastructure only for appearance. The analysis service itself is isolated so it can later move behind a dedicated worker without changing the visual domain pipeline.

Temporary storage/network failures are marked separately from permanent malformed-media failures. An authorized admin/reviewer retry endpoint can re-run the current algorithm version.

## API

Authorized ADMIN/REVIEWER users can retrieve:

```text
GET /api/v1/sessions/{sessionId}/visual-analysis
```

and request a background retry with:

```text
POST /api/v1/sessions/{sessionId}/visual-analysis/retry
```

The response exposes visual evidence only: status, visual direction, approximate magnitude, confidence, continuity and authorized diagnostics. It does not calculate sensor-camera consistency.

## Reviewer dashboard

The inspection verification panel keeps two explicit sections:

```text
LIVE CHALLENGES · SENSOR EVIDENCE
VISUAL MOTION ANALYSIS · CAMERA EVIDENCE
```

This makes the Phase 6 boundary visible to reviewers. The dashboard explicitly states that final authenticity and sensor-camera consistency are not yet calculated.

## Audit events

Phase 5 records:

```text
VISUAL_ANALYSIS_STARTED
VISUAL_ANALYSIS_COMPLETED
VISUAL_ANALYSIS_INCONCLUSIVE
VISUAL_ANALYSIS_FAILED
```

Raw frames and raw optical-flow arrays are not copied into the audit log.

## Deterministic tests

Automated tests cover:

- challenge/video timeline mapping;
- horizontal and vertical visual direction;
- synthetic affine rotation;
- low-feature scenes;
- RANSAC foreground outliers;
- scene cuts;
- duplicate/frozen frames;
- corrupted media;
- video metadata inspection;
- sampled-frame timestamp retention.

Synthetic tests prove implementation behavior, not real-world accuracy.

## Required real-video validation

Phase 5 must not be accepted from synthetic data alone. A physical Android phone must record SiteProof sessions and the uploaded `capture.mp4` must be processed by this backend. Results must be measured for real right/left/tilt challenges, different scenes and lighting conditions.

Until those trials are performed, real-video accuracy, false-direction rate and processing performance remain **NOT TESTED YET**.

## Known limitations

- low light can remove stable features;
- motion blur can break optical flow;
- blank walls, sky and smooth surfaces can be textureless;
- large independently moving foreground objects can reduce dominant-transform support;
- autofocus may create small apparent scale changes;
- rolling shutter can distort fast phone motion;
- approximate yaw/pitch magnitude depends on scene geometry and an assumed field of view;
- monocular visual motion is not calibrated 3D camera pose;
- a visually convincing motion does not prove physical sensors agree.

The challenge wording therefore asks the inspector to move slowly and smoothly while keeping the site visible.

## Phase 6 readiness boundary

After a real Phase 5 session is accepted, each challenge will have two independent measurements on the same synchronized session timeline:

```text
Phase 4: sensor-derived physical movement
Phase 5: visual-derived camera/scene movement
```

Phase 6 may compare those two signals. Phase 5 does not perform that comparison.
