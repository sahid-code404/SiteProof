package com.siteproof.app.verification.evidence

import android.os.Build
import android.os.Debug
import com.siteproof.app.BuildConfig
import com.siteproof.app.data.InspectionDetail
import com.siteproof.app.verification.environment.EnvironmentSnapshot
import com.siteproof.app.verification.model.CaptureCompleteRequest
import com.siteproof.app.verification.model.ChallengeTimelineMetadata
import com.siteproof.app.verification.model.DeviceCapabilities
import com.siteproof.app.verification.model.EvidenceFileDescriptor
import com.siteproof.app.verification.model.EvidencePackage
import java.io.File
import java.time.Instant
import org.json.JSONArray
import org.json.JSONObject

class EvidencePackager {
    fun packageEvidence(
        directory: File,
        sessionId: String,
        inspection: InspectionDetail,
        captureStartedAt: Instant,
        captureEndedAt: Instant,
        captureStartMonotonicNs: Long,
        videoStartMonotonicNs: Long,
        videoEndMonotonicNs: Long,
        capabilities: DeviceCapabilities,
        captureComplete: CaptureCompleteRequest,
        challenges: List<ChallengeTimelineMetadata> = emptyList(),
        environmentSnapshots: List<EnvironmentSnapshot> = emptyList(),
    ): EvidencePackage {
        val video = File(directory, "capture.mp4")
        val sensors = File(directory, "sensors.ndjson.gz")
        val locations = File(directory, "locations.json.gz")
        require(video.isFile && video.length() > 0) { "Live video file is missing." }
        require(sensors.isFile && sensors.length() > 0) { "Sensor evidence file is missing." }
        require(locations.isFile && locations.length() > 0) { "Location evidence file is missing." }

        val metadata = File(directory, "metadata.json")
        val metadataJson = JSONObject().apply {
            put("sessionId", sessionId)
            put("inspectionId", inspection.id)
            put("capture", JSONObject().apply {
                put("startedAt", captureStartedAt.toString())
                put("endedAt", captureEndedAt.toString())
                put("durationMs", captureComplete.captureDurationMs)
                put("monotonicStartNs", captureStartMonotonicNs)
                put(
                    "videoStartRelativeNs",
                    (videoStartMonotonicNs - captureStartMonotonicNs).coerceAtLeast(0L),
                )
                put(
                    "videoEndRelativeNs",
                    (videoEndMonotonicNs - captureStartMonotonicNs).coerceAtLeast(0L),
                )
            })
            put("device", JSONObject().apply {
                put("manufacturer", Build.MANUFACTURER)
                put("brand", Build.BRAND)
                put("model", Build.MODEL)
                put("device", Build.DEVICE)
                put("product", Build.PRODUCT)
                put("hardware", Build.HARDWARE)
                put("fingerprint", Build.FINGERPRINT)
                put("buildTags", Build.TAGS ?: "")
                put("buildType", Build.TYPE)
                put("androidVersion", Build.VERSION.RELEASE)
                put("sdkInt", Build.VERSION.SDK_INT)
                put("appVersion", BuildConfig.VERSION_NAME)
                put("debugBuild", BuildConfig.DEBUG)
                put("debuggerConnected", Debug.isDebuggerConnected())
                put("emulatorHeuristic", isLikelyEmulator())
                put("testKeys", Build.TAGS?.contains("test-keys", ignoreCase = true) == true)
                put("rootHeuristic", hasRootBinaryHeuristic())
            })
            put("camera", JSONObject().apply {
                put("lens", "BACK")
                put("audio", false)
            })
            put("sensors", JSONObject().apply {
                put("accelerometer", capabilities.accelerometer)
                put("gyroscope", capabilities.gyroscope)
                put("rotationVector", capabilities.rotationVector)
                put("magnetometer", capabilities.magnetometer)
            })
            put("environment", JSONObject().apply {
                put("version", "wifi-environment-v1")
                put("privacy", "session-scoped AP hashes; SSID/raw BSSID not stored")
                put("snapshots", JSONArray().apply {
                    environmentSnapshots.forEach { snapshot ->
                        put(JSONObject().apply {
                            put("capturedAtEpochMs", snapshot.capturedAtEpochMs)
                            put("wifiEnabled", snapshot.wifiEnabled)
                            put("permissionGranted", snapshot.permissionGranted)
                            put("accessPoints", JSONArray().apply {
                                snapshot.accessPoints.forEach { accessPoint ->
                                    put(JSONObject().apply {
                                        put("apHash", accessPoint.apHash)
                                        put("rssiDbm", accessPoint.rssiDbm)
                                        put("frequencyMhz", accessPoint.frequencyMhz)
                                    })
                                }
                            })
                        })
                    }
                })
            })
            put("sensorSummary", JSONObject().apply {
                put("accelerometerSamples", captureComplete.sensorSummary.accelerometerSamples)
                put("gyroscopeSamples", captureComplete.sensorSummary.gyroscopeSamples)
                put("rotationVectorSamples", captureComplete.sensorSummary.rotationVectorSamples)
                put("magnetometerSamples", captureComplete.sensorSummary.magnetometerSamples)
            })
            put("locationSummary", JSONObject().apply {
                put("locationSamples", captureComplete.locationSummary.locationSamples)
                captureComplete.locationSummary.bestAccuracyMeters?.let { put("bestAccuracyMeters", it) }
                captureComplete.locationSummary.firstRelativeTimestampNs?.let { put("firstRelativeTimestampNs", it) }
                captureComplete.locationSummary.lastRelativeTimestampNs?.let { put("lastRelativeTimestampNs", it) }
            })
            put("challenges", JSONArray().apply {
                challenges.forEach { item ->
                    put(JSONObject().apply {
                        put("id", item.id)
                        put("type", item.type)
                        put("issuedRelativeMs", item.issuedRelativeMs)
                        item.startedRelativeMs?.let { put("startedRelativeMs", it) }
                        item.completedRelativeMs?.let { put("completedRelativeMs", it) }
                        item.result?.let { put("result", it) }
                        item.score?.let { put("score", it) }
                    })
                }
            })
        }
        metadata.writeText(metadataJson.toString(), Charsets.UTF_8)

        val descriptorsWithoutManifest = listOf(
            descriptor("VIDEO", video, "video/mp4"),
            descriptor("SENSOR_DATA", sensors, "application/octet-stream"),
            descriptor("LOCATION_DATA", locations, "application/gzip"),
            descriptor("SESSION_METADATA", metadata, "application/json"),
        )
        val manifest = File(directory, "manifest.json")
        val manifestJson = JSONObject().apply {
            put("sessionId", sessionId)
            put("files", JSONArray().apply {
                descriptorsWithoutManifest.forEach { descriptor ->
                    put(JSONObject().apply {
                        put("type", descriptor.type)
                        put("name", descriptor.filename)
                        put("sizeBytes", descriptor.sizeBytes)
                        put("sha256", descriptor.sha256)
                    })
                }
            })
        }
        manifest.writeText(manifestJson.toString(), Charsets.UTF_8)
        val manifestDescriptor = descriptor("MANIFEST", manifest, "application/json")
        return EvidencePackage(
            directoryPath = directory.absolutePath,
            files = descriptorsWithoutManifest + manifestDescriptor,
            manifestSha256 = manifestDescriptor.sha256,
            captureComplete = captureComplete,
        )
    }

    private fun isLikelyEmulator(): Boolean {
        val fields = listOf(
            Build.FINGERPRINT,
            Build.MODEL,
            Build.MANUFACTURER,
            Build.BRAND,
            Build.DEVICE,
            Build.PRODUCT,
            Build.HARDWARE,
        ).joinToString(" ").lowercase()
        return listOf(
            "generic",
            "emulator",
            "sdk_gphone",
            "goldfish",
            "ranchu",
            "genymotion",
        ).any(fields::contains)
    }

    private fun hasRootBinaryHeuristic(): Boolean {
        val paths = listOf(
            "/system/bin/su",
            "/system/xbin/su",
            "/sbin/su",
            "/su/bin/su",
            "/data/local/bin/su",
            "/data/local/xbin/su",
        )
        return paths.any { path -> runCatching { File(path).exists() }.getOrDefault(false) }
    }

    private fun descriptor(type: String, file: File, mime: String): EvidenceFileDescriptor =
        EvidenceFileDescriptor(
            type = type,
            filename = file.name,
            sizeBytes = file.length(),
            sha256 = EvidenceHasher.sha256(file),
            mimeType = mime,
        )
}
