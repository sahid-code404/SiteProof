# Phase 3 Evidence Format

## Local package

Every capture is written into app-private storage:

```text
session_<uuid>/
├── capture.mp4
├── sensors.ndjson.gz
├── locations.json.gz
├── metadata.json
└── manifest.json
```

No Phase 3 file is copied to Gallery, Downloads or DCIM.

## `capture.mp4`

Rear-camera CameraX video without audio. The backend expects MIME type `video/mp4`. The prototype maximum is 100 MiB.

## `sensors.ndjson.gz`

Gzip-compressed newline-delimited JSON. Each row contains the real Android sensor timestamp and its offset from the session monotonic anchor:

```json
{"type":"GYROSCOPE","sensorTimestampNs":8812344001000,"relativeTimestampNs":321000000,"values":[0.024,0.712,-0.103],"accuracy":3}
```

Types used in Phase 3 are `ACCELEROMETER`, `GYROSCOPE`, `ROTATION_VECTOR`, and optional `MAGNETOMETER`. The backend parses the compressed package, rejects negative/decreasing timestamps per sensor stream, and checks sample counts against the capture summary.

## `locations.json.gz`

Gzip-compressed JSON array. A sample contains:

```json
{
  "relativeTimestampNs": 1050000000,
  "latitude": 22.5726,
  "longitude": 88.3639,
  "accuracyMeters": 8.2,
  "altitudeMeters": 12.4,
  "bearingDegrees": 92.0,
  "speedMetersPerSecond": 0.4
}
```

Optional values are omitted when Android does not provide them. The backend validates coordinate ranges, non-negative accuracy, monotonic relative timestamps and sample count.

## `metadata.json`

Contains identifiers and synchronization/capability metadata, including:

- session ID and inspection ID;
- wall-clock capture start/end;
- capture duration;
- monotonic T0;
- video-start relative offset;
- manufacturer/model/Android/app version as metadata only;
- rear-camera lens and `audio=false`;
- sensor capability flags;
- sensor and location sample summaries.

Device model is never treated as identity proof.

## `manifest.json`

The manifest lists the four non-manifest evidence objects with exact filename, compressed/uploaded byte size and SHA-256. It intentionally does not recursively list itself.

```json
{
  "sessionId": "...",
  "files": [
    {"type":"VIDEO","name":"capture.mp4","sizeBytes":7348821,"sha256":"..."},
    {"type":"SENSOR_DATA","name":"sensors.ndjson.gz","sizeBytes":182341,"sha256":"..."}
  ]
}
```

After writing the manifest, the Android app computes SHA-256 of the manifest itself. Hashes always correspond to the exact bytes uploaded; sensor/location hashes therefore cover compressed bytes.

## Server-side object metadata

PostgreSQL stores evidence metadata only: organization/inspection/session IDs, file type, non-user-controlled object key, original filename, MIME type, size, SHA-256, upload state and timestamps. Video/sensor/location blobs remain outside PostgreSQL.

Object keys are generated server-side under a hierarchy such as:

```text
organizations/<org>/inspections/<inspection>/sessions/<session>/video/<uuid>.mp4
```

## Upload integrity

1. Android sends descriptors and an idempotency key.
2. Server creates/reuses one evidence record per session/file type.
3. Android streams each file to its authorized target.
4. Backend streams the request into temporary storage while independently calculating SHA-256.
5. Size/hash must match the declared descriptor before the object is accepted.
6. On completion the backend parses manifest/sensor/location/metadata structure before moving the session to `UPLOADED`.

A hash sent by Android alone is never accepted as proof of file integrity.
