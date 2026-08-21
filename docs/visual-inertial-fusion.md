# Phase 6 Visual–Inertial Fusion

## Purpose and security boundary

Phase 6 compares two independently produced measurements for the same randomized challenge:

```text
Phase 4 physical phone motion
  gyroscope + rotation vector + sensor quality
                VS
Phase 5 visible scene/camera motion
  video + optical flow + global visual transform
```

The question is deliberately narrow:

> Did the camera-visible movement correspond to the physical movement measured by the phone?

Phase 6 returns cross-signal consistency. It does **not** return an overall SiteProof trust score, `VERIFIED`, `FLAGGED`, `AUTHENTIC`, or a final replay-attack verdict. Those decisions belong to later phases.

## Reused evidence and common timeline

Phase 6 does not rebuild Phase 4 or Phase 5.

Phase 4 already persists backend-derived challenge measurements such as:

- gyroscope integrated angle;
- rotation-vector angle delta;
- sensor agreement;
- sensor confidence/quality;
- challenge result and server/client timing metadata.

Phase 5 already persists:

- physical-camera semantic direction;
- approximate visual angular change;
- visual motion start/end;
- visual confidence/quality;
- scene continuity;
- a session-time visual motion curve.

Android also uploads the full hashed `sensors.ndjson.gz` from the same capture anchor. Each gyroscope sample contains `relativeTimestampNs`, so the backend can derive the one Phase 4 feature that was not previously persisted at high rate: the sensor motion curve and sensor movement start/peak/end timestamps.

The Phase 4 stored angle/confidence remain authoritative. Phase 6 does not replace them with an Android summary.

## Common motion representation

Both sources are converted into the same conceptual structure:

```text
MotionEstimate
  direction
  angular_change_deg
  start_ms
  peak_ms
  end_ms
  confidence
  source
  quality
  kind
  motion curve
```

Supported primary motion kinds are:

```text
ROTATION
TILT
```

Translation is intentionally not required for this phase.

## Coordinate normalization

Raw image motion and physical camera motion can have opposite signs. For example, a camera yaw to the right often moves a static scene to the left in image coordinates.

Phase 5 already converts its optical-flow/global-transform output to physical-camera semantics. Phase 6 still routes that value through one dedicated function:

```text
normalize_visual_to_camera_motion(...)
```

This prevents future sign conversions from being scattered through the fusion code.

Sensor normalization uses the same Phase 4 axis/sign configuration:

```text
ROTATE: gyroscope Y axis
TILT:   gyroscope X axis

ROTATION_RIGHT_SIGN
TILT_DOWN_SIGN
```

The normalized result is always semantic physical-camera movement:

```text
LEFT
RIGHT
UP
DOWN
NONE
MIXED
```

## Sensor timing curve

The backend reads only the previously SHA-256-verified `SENSOR_DATA` evidence record.

The compressed object is size-limited and decompression also has a configured upper bound. Only gyroscope rows are retained for fusion.

For the current challenge window:

1. choose the same session-time window used by Phase 5 where available;
2. select gyroscope samples from that window;
3. apply the Phase 4 axis/sign convention;
4. estimate a baseline bias from the initial quiet portion;
5. use absolute debiased angular velocity as motion energy;
6. locate movement onset with the existing Phase 4 movement threshold;
7. locate settling with the existing settle threshold/time;
8. retain sample count and maximum timestamp gap as quality diagnostics.

This curve is for timing/shape comparison. The Phase 4 integrated angle is not recalculated from it.

## Direction consistency

Direction comparison is deterministic:

```text
same semantic direction       1.0
NONE / MIXED uncertainty      0.5
opposite semantic direction   0.0
```

If both sources have high confidence and point in opposite directions, Phase 6 records:

```text
OPPOSITE_DIRECTION
```

and forces a `MISMATCH` state.

## Magnitude consistency

For approximate angular movement:

```text
absolute_error =
|sensor_angle - visual_angle|

relative_error =
absolute_error / max(|sensor_angle|, 1 degree)
```

The initial configurable absolute-error anchors are:

```text
<= 8°   strong agreement region
>= 25°  maximum-error region
```

Between them, the absolute score falls linearly. Relative error is a secondary penalty because visual monocular angle is approximate.

The combined prototype magnitude score gives more weight to absolute error for the current 22–55 degree challenge range.

These are starting values, not measured device thresholds.

## Temporal consistency

The signed offsets are retained:

```text
start_offset_ms =
visual_start_ms - sensor_start_ms

end_offset_ms =
visual_end_ms - sensor_end_ms
```

Absolute offset is used for scoring, while the sign remains available to diagnose whether camera motion appears earlier or later.

Initial configurable timing anchors:

```text
<= 150 ms     excellent
150–350 ms    good
350–700 ms    weak
> 700 ms      suspicious timing mismatch
```

These values must be tuned from real devices. At a 10 FPS visual stream, frame-level timing resolution is already around 100 ms, so Phase 6 does not claim millisecond-perfect synchronization.

## Duration consistency

Duration is independently compared:

```text
sensor_duration = sensor_end - sensor_start
visual_duration = visual_end - visual_start
```

The comparator uses relative duration error. Large disagreement can add:

```text
DURATION_MISMATCH
```

## Motion-curve resampling

Gyroscope and visual motion have different sampling rates and units.

Before shape comparison, each curve is independently normalized:

```text
remove initial baseline
clip negative energy to zero
divide by maximum remaining magnitude
```

This produces unitless motion shape in the range 0–1.

Both normalized curves are interpolated onto a common configurable timeline:

```text
FUSION_RESAMPLE_HZ=20
```

Interpolation does not claim that the camera originally sampled at 20 Hz. It only creates common evaluation points over overlapping observed time.

## Pearson correlation

At zero lag, Phase 6 computes ordinary Pearson correlation where enough non-flat samples overlap:

```text
r ~= +1   similar motion shape
r ~=  0   little linear shape relationship
r ~= -1   opposite shape relationship
```

Correlation alone never decides authenticity.

## Limited-lag cross-correlation

A small real sensor-camera offset may exist. Phase 6 therefore evaluates correlation at limited candidate lags:

```text
FUSION_MAX_ALIGNMENT_LAG_MS=500
```

A positive `bestLagMs` means the visual curve occurs later than the sensor curve.

The system chooses the best correlation only inside this bounded lag window. It never shifts curves by several seconds merely to manufacture a high correlation.

## Consistency score

The default normalized component weights are:

```text
direction       25%
magnitude       25%
timing          20%
correlation     20%
duration        10%
```

If an optional component cannot be measured, the available weights are normalized for the raw score, and the missing coverage lowers fusion confidence.

The default status thresholds are:

```text
>= 0.80   CONSISTENT
>= 0.60   PARTIALLY_CONSISTENT
<  0.60   MISMATCH
```

Low source quality overrides numerical score and returns `INCONCLUSIVE`.

## Consistency versus confidence

Phase 6 exposes two separate values:

```text
consistencyScore
fusionConfidence
```

`consistencyScore` answers how well the measurable signals agree.

`fusionConfidence` answers how strongly the available sensor/visual evidence supports making that comparison.

Fusion confidence combines:

- the geometric mean of the two source confidences;
- the weaker source confidence;
- comparison-component coverage.

It is not a blind product and it does not turn agreement into an authenticity score.

## Strong contradiction rules

High-confidence contradictions are explicitly classified.

### Opposite movement

```text
Sensor: RIGHT
Vision: LEFT
```

Reason:

```text
OPPOSITE_DIRECTION
```

### Visual movement without physical movement

```text
Sensor angle near zero
Visual angle large
```

Reason:

```text
VISUAL_WITHOUT_SENSOR_MOTION
```

This is useful for a future replay-risk engine, but Phase 6 does **not** label it a replay attack.

### Physical movement without visual movement

```text
Sensor angle large
Visual angle near zero
```

Reason:

```text
SENSOR_WITHOUT_VISUAL_MOTION
```

If visual quality is poor, the result becomes `INCONCLUSIVE` instead of an accusation.

## Other structured reasons

Phase 6 can also record:

```text
MAGNITUDE_MISMATCH
TEMPORAL_MISMATCH
DURATION_MISMATCH
LOW_SENSOR_QUALITY
LOW_VISUAL_QUALITY
SCENE_CONTINUITY_ANOMALY
CURVE_UNAVAILABLE
```

Multiple reasons may apply to the same challenge.

Scene continuity is supporting evidence only. A freeze or continuity anomaly lowers confidence but does not dominate the cross-signal decision by itself.

## Persistence and idempotency

Migration:

```text
0006_phase6_visual_inertial
```

Table:

```text
visual_inertial_results
```

Important measurements are typed columns. Normalized curves and explainability details are diagnostics JSON.

Current algorithm identity:

```text
fusion-v1.0
```

Uniqueness:

```text
challenge_id + fusion_version
```

Re-running the same version updates the same logical result. A later algorithm version can coexist without silently changing the historical meaning of an older score.

## Background pipeline

The verified-evidence path now runs:

```text
evidence upload + SHA-256 verification
              ↓
Phase 5 visual analysis
              ↓
visual terminal result
              ↓
Phase 6 fusion
              ↓
visual_inertial_results
```

Fusion will not calculate a comparison while a challenge's Phase 4 or Phase 5 input is still pending.

A technical fusion failure is stored as `FAILED`; it is never reinterpreted as `MISMATCH`.

An authorized retry endpoint re-runs the current version idempotently. A Phase 5 reanalysis also forces the dependent Phase 6 result to be recomputed.

## API

Authorized `ADMIN` / `REVIEWER` users can retrieve:

```text
GET /api/v1/sessions/{sessionId}/fusion-analysis
```

and request current-version reanalysis:

```text
POST /api/v1/sessions/{sessionId}/fusion-analysis/retry
```

The response includes per-challenge sensor/visual angles and directions, signed timing offsets, duration, best limited-lag correlation, component scores, consistency score, fusion confidence, mismatch reasons, explanations, and normalized curve points.

The API deliberately does not contain a final SiteProof trust score or verification verdict.

## Reviewer dashboard

The reviewer page now presents three distinct evidence layers:

```text
LIVE CHALLENGES · SENSOR EVIDENCE
VISUAL MOTION ANALYSIS · CAMERA EVIDENCE
CROSS-SIGNAL ANALYSIS · PHYSICAL VS CAMERA
```

The Phase 6 section shows sensor and camera motion side by side, angle difference, start/end offsets, best limited-lag correlation, consistency, fusion confidence, structured reasons, and a lightweight SVG plot of the normalized sensor and camera curves.

No charting dependency was added solely for this graph.

The page still states that final authenticity is not yet calculated.

## Audit events

Phase 6 records:

```text
FUSION_ANALYSIS_STARTED
FUSION_ANALYSIS_COMPLETED
FUSION_ANALYSIS_INCONCLUSIVE
FUSION_MISMATCH_DETECTED
FUSION_ANALYSIS_FAILED
```

Complete motion arrays are not copied into audit logs.

## Automated tests

Deterministic automated coverage includes:

- same/uncertain/opposite direction comparison;
- close and large angle disagreement;
- signed timing offsets;
- duration comparison;
- 20 Hz resampling;
- Pearson/cross-correlation and limited lag;
- delayed/scaled/noisy legitimate curves;
- opposite-direction contradiction;
- visual-only movement;
- sensor-only movement;
- low-confidence inconclusive behavior;
- large timing mismatch;
- unavailable curve behavior;
- Phase 4 + Phase 5 to persisted Phase 6 integration;
- challenge/version idempotency;
- reviewer/admin authorization;
- inspector denial;
- cross-organization isolation;
- missing-result `PENDING` API behavior;
- web curve rendering with missing data.

Synthetic tests prove deterministic implementation behavior, not real-world attack-detection accuracy.

## Real-device and attack acceptance

Phase 6 is **not accepted** from CI or synthetic data alone.

Required physical validation still includes at least:

1. one genuine randomized SiteProof challenge where real sensor and real video evidence produce a defensible `CONSISTENT` result;
2. one controlled video-on-screen experiment where visible movement occurs without corresponding physical motion and the measured evidence produces a defensible inconsistency where expected;
3. repeated legitimate ROTATE_RIGHT / ROTATE_LEFT / TILT_UP / TILT_DOWN trials where practical;
4. actual angle-error, timing-offset and correlation distributions;
5. actual processing time measurements;
6. device model, Android version, sensor availability and camera FPS;
7. multiple Android devices where available.

No real-device result, attack result, false-positive rate, threshold distribution, or performance number may be fabricated.

## Known limitations

Visual-inertial consistency makes simple replay scenarios harder, but does not make SiteProof impossible to spoof.

Residual risks include:

- physically synchronized replay;
- sensor manipulation;
- modified or instrumented OS/device;
- a static screen filmed while the phone physically moves;
- camera rolling shutter and motion blur;
- low-texture or low-light scenes;
- systematic camera/sensor latency;
- monocular visual-angle approximation;
- different sensor characteristics across Android devices.

A static screen while the phone moves may produce both sensor and visual motion and can pass basic fusion. Later replay/screen heuristics must address that separately.

## Viva-friendly explanation

Suppose:

```text
Gyroscope: 42°
Camera:    39°
```

The magnitude difference is 3 degrees, so magnitude agreement is high.

Then:

```text
Sensor movement starts: 4.20 s
Visual movement starts: 4.31 s
```

The start difference is 110 ms, so timing agreement is high.

After independently normalizing the two motion curves:

```text
best correlation = 0.89
best lag = +100 ms
```

If direction and duration also agree, the weighted cross-signal consistency can be high.

That still means only:

> the two independent motion sources were mutually consistent.

It does not, by itself, prove that the whole SiteProof submission is authentic.

## Phase 7 boundary

Once real Phase 6 acceptance is recorded, the project can have independent usable signals for:

```text
location
challenge completion
sensor motion
visual motion
visual-inertial consistency
scene continuity
```

Phase 7 may then combine independent signals into the final explainable SiteProof verification engine.

Phase 6 does not perform that combination.
