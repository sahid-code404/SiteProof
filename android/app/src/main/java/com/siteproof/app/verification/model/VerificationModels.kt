package com.siteproof.app.verification.model

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = false)
data class DeviceCapabilities(
    val accelerometer: Boolean,
    val gyroscope: Boolean,
    val rotationVector: Boolean,
    val magnetometer: Boolean = false,
)

@JsonClass(generateAdapter = false)
data class CaptureLocation(
    val latitude: Double,
    val longitude: Double,
    val accuracyMeters: Double,
    val altitudeMeters: Double? = null,
    val bearingDegrees: Double? = null,
    val speedMetersPerSecond: Double? = null,
    val capturedAt: String? = null,
    val elapsedRealtimeNs: Long? = null,
)

@JsonClass(generateAdapter = false)
data class SessionCreateRequest(
    val deviceSessionId: String,
    val clientTime: String,
    val clientMonotonicNs: Long,
    val clientVersion: String,
    val androidVersion: String,
    val deviceModel: String,
)

@JsonClass(generateAdapter = false)
data class SessionCreateResponse(
    val sessionId: String,
    val inspectionId: String,
    val status: String,
    val expiresAt: String,
    val serverTime: String,
    val clockOffsetMs: Double? = null,
)

@JsonClass(generateAdapter = false)
data class StartCaptureRequest(
    val clientWallClock: String,
    val clientMonotonicNs: Long,
    val location: CaptureLocation,
    val capabilities: DeviceCapabilities,
)

@JsonClass(generateAdapter = false)
data class SensorSummary(
    val accelerometerSamples: Int,
    val gyroscopeSamples: Int,
    val rotationVectorSamples: Int,
    val magnetometerSamples: Int = 0,
)

@JsonClass(generateAdapter = false)
data class LocationSummary(
    val locationSamples: Int,
    val bestAccuracyMeters: Double? = null,
    val firstRelativeTimestampNs: Long? = null,
    val lastRelativeTimestampNs: Long? = null,
)

@JsonClass(generateAdapter = false)
data class CaptureCompleteRequest(
    val captureDurationMs: Long,
    val videoFileCount: Int = 1,
    val sensorSummary: SensorSummary,
    val locationSummary: LocationSummary,
)

@JsonClass(generateAdapter = false)
data class AbortRequest(val reason: String)

@JsonClass(generateAdapter = false)
data class EvidencePresence(
    val video: Boolean = false,
    val sensorData: Boolean = false,
    val locationData: Boolean = false,
    val sessionMetadata: Boolean = false,
    val manifest: Boolean = false,
)

@JsonClass(generateAdapter = false)
data class VerificationSession(
    val id: String,
    val inspectionId: String,
    val inspectorId: String,
    val status: String,
    val createdAt: String,
    val captureStartedAt: String? = null,
    val captureEndedAt: String? = null,
    val uploadedAt: String? = null,
    val expiresAt: String,
    val captureDurationMs: Long? = null,
    val manifestSha256: String? = null,
    val sensorSummary: SensorSummary? = null,
    val locationSummary: LocationSummary? = null,
    val evidence: EvidencePresence = EvidencePresence(),
)

@JsonClass(generateAdapter = false)
data class EvidenceFileDescriptor(
    val type: String,
    val filename: String,
    val sizeBytes: Long,
    val sha256: String,
    val mimeType: String,
)

@JsonClass(generateAdapter = false)
data class EvidenceInitiateRequest(
    val idempotencyKey: String,
    val files: List<EvidenceFileDescriptor>,
)

@JsonClass(generateAdapter = false)
data class EvidenceUploadTarget(
    val fileId: String,
    val type: String,
    val uploadPath: String,
    val method: String,
    val alreadyUploaded: Boolean = false,
)

@JsonClass(generateAdapter = false)
data class EvidenceInitiateResponse(
    val sessionId: String,
    val status: String,
    val targets: List<EvidenceUploadTarget>,
)

@JsonClass(generateAdapter = false)
data class EvidenceCompleteRequest(val manifestSha256: String)

@JsonClass(generateAdapter = false)
data class EvidenceFileResponse(
    val id: String,
    val type: String,
    val filename: String,
    val mimeType: String,
    val sizeBytes: Long,
    val sha256: String,
    val uploadStatus: String,
    val hashVerified: Boolean,
    val uploadedAt: String? = null,
    val downloadPath: String? = null,
)

@JsonClass(generateAdapter = false)
data class EvidenceListResponse(
    val sessionId: String,
    val items: List<EvidenceFileResponse>,
)

data class SensorCounts(
    val accelerometer: Int = 0,
    val gyroscope: Int = 0,
    val rotationVector: Int = 0,
    val magnetometer: Int = 0,
) {
    fun toApi() = SensorSummary(accelerometer, gyroscope, rotationVector, magnetometer)
}

data class CapturedLocationSample(
    val relativeTimestampNs: Long,
    val latitude: Double,
    val longitude: Double,
    val accuracyMeters: Double,
    val altitudeMeters: Double? = null,
    val bearingDegrees: Double? = null,
    val speedMetersPerSecond: Double? = null,
)

data class LocationReadiness(
    val location: CaptureLocation,
    val ageSeconds: Double,
    val distanceMeters: Double,
    val accuracyLabel: String,
    val withinAllowedArea: Boolean,
    val inconclusive: Boolean,
)

data class EvidencePackage(
    val directoryPath: String,
    val files: List<EvidenceFileDescriptor>,
    val manifestSha256: String,
    val captureComplete: CaptureCompleteRequest,
)
