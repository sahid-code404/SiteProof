# Phase 3 Live Capture

## Purpose

Phase 3 collects live field evidence; it does not decide authenticity. The Android client records a short rear-camera video together with motion sensors and GPS on one relative monotonic timeline, packages the outputs in app-private storage, hashes them, and schedules reliable upload.

## Permissions and privacy

Requested at verification time only:

- `CAMERA`
- `ACCESS_FINE_LOCATION`
- `ACCESS_COARSE_LOCATION`

No microphone permission is requested. CameraX recording is intentionally created without audio so unrelated conversations are not captured. No gallery/document picker exists in the verification flow.

`FLAG_SECURE` is applied while the verification screen is visible as a privacy/discouragement measure. It is not treated as replay-attack prevention.

## Readiness sequence

1. Inspector opens an inspection whose server state is `READY`.
2. App explains camera/location/sensor use and requests runtime permissions.
3. `SensorManager` reports actual device capabilities. Missing sensors are reported rather than fabricated.
4. `FusedLocationProviderClient.getCurrentLocation` obtains a high-accuracy location.
5. Location age must be at most 10 seconds for the default prototype configuration.
6. Accuracy is displayed as Good (<=20 m), Moderate (21–50 m), or Poor (>50 m).
7. Haversine distance is compared to expected coordinates and radius. If `distance > radius + accuracy`, capture is blocked. If only the uncertainty band crosses the radius, the result is inconclusive and the inspector must retry.
8. Server creates a short-lived verification session.
9. CameraX binds the rear camera preview.

## Capture timeline

At capture start the client records `T0 = SystemClock.elapsedRealtimeNanos()`. Server `start-capture` receives the same monotonic anchor and a wall-clock timestamp, but the server receipt time remains authoritative.

Sensor events use Android's monotonic `SensorEvent.timestamp` and store:

```text
relativeTimestampNs = sensorTimestampNs - T0
```

Location samples use `Location.elapsedRealtimeNanos` and the same T0. Camera recording is started directly into an app-private MP4 file, and metadata records the video-start offset from T0.

## Sensors

`SensorRecorder` requests approximately 50 Hz using a 20,000 microsecond sampling period. Actual timestamps are stored; the implementation does not assume the hardware reaches exactly 50 Hz. Accelerometer is required by Phase 3. Gyroscope and rotation vector are recorded when available and their absence is reported as reduced capability. Magnetometer is optional.

Sensor records are streamed directly into `sensors.ndjson.gz`; a giant in-memory `List<SensorEvent>` is never built. Listeners are unregistered on normal stop, abort and release.

## Location during capture

High-accuracy updates are requested about once per second. The session is short (8–60 seconds), so location samples may be held briefly in memory and are written to `locations.json.gz` when capture stops. Location updates are always removed after stop/abort.

## Camera

CameraX `Preview` + `VideoCapture<Recorder>` uses the rear camera. Quality selection prefers FHD, then HD/SD fallbacks for stability. Audio is disabled. Output is written directly to `filesDir/verification/session_<uuid>/capture.mp4`.

Capture limits:

- minimum: 8 seconds;
- recommended: 15–30 seconds;
- maximum accepted by backend: 60 seconds.

## Interruption policy

If the verification Activity loses required foreground state during active capture, the client aborts the live capture and asks the server to mark the session `ABORTED`. The same capture is not resumed after a long interruption. User cancellation also requires an explicit confirmation.

Network loss after a completed recording is different: local evidence is retained and WorkManager retries upload. The user does not have to re-record simply because connectivity disappeared.
