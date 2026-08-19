package com.siteproof.app.verification

import android.content.Context
import android.os.SystemClock
import androidx.camera.view.PreviewView
import androidx.lifecycle.LifecycleOwner
import com.siteproof.app.data.InspectionDetail
import com.siteproof.app.verification.capture.CameraCaptureManager
import com.siteproof.app.verification.evidence.EvidencePackager
import com.siteproof.app.verification.location.LocationRecorder
import com.siteproof.app.verification.model.ChallengeIssue
import com.siteproof.app.verification.model.ChallengeSensorWindow
import com.siteproof.app.verification.model.ChallengeSubmitRequest
import com.siteproof.app.verification.model.ChallengeTimelineMetadata
import com.siteproof.app.verification.model.ChallengeValidationResult
import com.siteproof.app.verification.model.DeviceCapabilities
import com.siteproof.app.verification.model.EvidencePackage
import com.siteproof.app.verification.model.LocationReadiness
import com.siteproof.app.verification.model.SessionCreateResponse
import com.siteproof.app.verification.sensors.SensorRecorder
import com.siteproof.app.verification.upload.EvidenceUploadWorker
import java.io.File
import java.time.Instant
import java.util.UUID
import org.json.JSONArray
import org.json.JSONObject

class VerificationCaptureCoordinator(
    private val context: Context,
    private val repository: VerificationRepository,
    private val sensorRecorder: SensorRecorder = SensorRecorder(context),
    private val locationRecorder: LocationRecorder = LocationRecorder(context),
    private val cameraManager: CameraCaptureManager = CameraCaptureManager(context),
    private val packager: EvidencePackager = EvidencePackager(),
) {
    data class Prepared(
        val inspection: InspectionDetail,
        val session: SessionCreateResponse,
        val location: LocationReadiness,
        val capabilities: DeviceCapabilities,
    )

    data class ActiveCapture(
        val prepared: Prepared,
        val directory: File,
        val captureStartNs: Long,
        val captureStartedAt: Instant,
    )

    data class ActiveChallenge(
        val issue: ChallengeIssue,
        val startedMonotonicNs: Long,
        val startRelativeNs: Long,
        val issuedRelativeMs: Long,
        val idempotencyKey: String,
    )

    private var active: ActiveCapture? = null
    private var activeChallenge: ActiveChallenge? = null
    private var pendingSubmission: ChallengeSubmitRequest? = null
    private val challengeTimeline = mutableListOf<ChallengeTimelineMetadata>()

    suspend fun prepare(inspectionId: String): Prepared {
        val inspection = repository.inspection(inspectionId)
        require(inspection.status == "READY") { "Inspection must be READY before live verification." }
        val capabilities = sensorRecorder.capabilities()
        require(capabilities.accelerometer) { "This device does not have an accelerometer." }
        val location = locationRecorder.freshLocation(
            inspection.expectedLatitude,
            inspection.expectedLongitude,
            inspection.allowedRadiusMeters,
        )
        if (!location.withinAllowedArea && !location.inconclusive) {
            throw IllegalStateException(
                "You are approximately ${location.distanceMeters.toInt()} m from the assigned inspection location.",
            )
        }
        val session = repository.createSession(inspectionId, UUID.randomUUID().toString())
        return Prepared(inspection, session, location, capabilities)
    }

    suspend fun bindCamera(previewView: PreviewView, lifecycleOwner: LifecycleOwner) {
        cameraManager.bind(previewView, lifecycleOwner)
    }

    suspend fun abandonPrepared(prepared: Prepared, reason: String = "USER_CANCELLED") {
        if (active == null) {
            repository.abort(prepared.session.sessionId, reason)
            cameraManager.release()
        }
    }

    suspend fun start(prepared: Prepared) {
        check(active == null) { "Capture is already active." }
        val fresh = locationRecorder.freshLocation(
            prepared.inspection.expectedLatitude,
            prepared.inspection.expectedLongitude,
            prepared.inspection.allowedRadiusMeters,
        )
        if (!fresh.withinAllowedArea) {
            if (fresh.inconclusive) {
                throw IllegalStateException("Location is inconclusive. Acquire a more accurate GPS position.")
            }
            throw IllegalStateException("Verification cannot begin outside the assigned location.")
        }
        val captureStartNs = SystemClock.elapsedRealtimeNanos()
        repository.startCapture(
            prepared.session.sessionId,
            captureStartNs,
            fresh.location,
            prepared.capabilities,
        )
        val directory = File(context.filesDir, "verification/session_${prepared.session.sessionId}").apply {
            deleteRecursively()
            mkdirs()
        }
        try {
            sensorRecorder.start(captureStartNs, File(directory, "sensors.ndjson.gz"))
            locationRecorder.startCapture(captureStartNs)
            cameraManager.startRecording(File(directory, "capture.mp4"))
            challengeTimeline.clear()
            activeChallenge = null
            pendingSubmission = null
            active = ActiveCapture(prepared, directory, captureStartNs, Instant.now())
        } catch (error: Exception) {
            cleanupCapture()
            repository.abort(prepared.session.sessionId, "CAMERA_ERROR")
            throw error
        }
    }

    fun captureElapsedMs(): Long {
        val capture = active ?: return 0L
        return (SystemClock.elapsedRealtimeNanos() - capture.captureStartNs) / 1_000_000L
    }

    suspend fun beginNextChallenge(): ChallengeIssue {
        val capture = checkNotNull(active) { "Capture is not active." }
        check(activeChallenge == null) { "A challenge is already active." }
        val issuedReceiveNs = SystemClock.elapsedRealtimeNanos()
        val issue = repository.issueChallenge(capture.prepared.session.sessionId)
        val startNs = SystemClock.elapsedRealtimeNanos()
        val startedIssue = repository.startChallenge(issue, startNs)
        val startRelativeNs = startNs - capture.captureStartNs
        activeChallenge = ActiveChallenge(
            issue = startedIssue,
            startedMonotonicNs = startNs,
            startRelativeNs = startRelativeNs,
            issuedRelativeMs = (issuedReceiveNs - capture.captureStartNs) / 1_000_000L,
            idempotencyKey = repository.challengeIdempotencyKey(capture.prepared.session.sessionId),
        )
        pendingSubmission = null
        return startedIssue
    }

    fun movementDetected(): Boolean {
        val challenge = activeChallenge ?: return false
        val nowRelative = sensorRecorder.relativeNowNs(SystemClock.elapsedRealtimeNanos())
        val baselineEnd = challenge.startRelativeNs + 500_000_000L
        if (nowRelative <= baselineEnd) return false
        return sensorRecorder.movementDetected(baselineEnd, nowRelative)
    }

    suspend fun submitCurrentChallenge(): ChallengeValidationResult {
        val capture = checkNotNull(active) { "Capture is not active." }
        val challenge = checkNotNull(activeChallenge) { "No challenge is active." }
        val request = pendingSubmission ?: buildSubmission(challenge).also { pendingSubmission = it }
        preserveChallengeEvidence(capture, challenge, request)
        val result = repository.submitChallenge(challenge.issue, request)
        val completedRelativeMs = captureElapsedMs()
        challengeTimeline += ChallengeTimelineMetadata(
            id = challenge.issue.challengeId,
            type = challenge.issue.type,
            issuedRelativeMs = challenge.issuedRelativeMs,
            startedRelativeMs = challenge.startRelativeNs / 1_000_000L,
            completedRelativeMs = completedRelativeMs,
            result = result.result,
            score = result.score,
        )
        pendingSubmission = null
        activeChallenge = null
        return result
    }

    suspend fun retryCurrentChallengeSubmission(): ChallengeValidationResult = submitCurrentChallenge()

    private fun buildSubmission(challenge: ActiveChallenge): ChallengeSubmitRequest {
        val endRelativeNs = sensorRecorder.relativeNowNs(SystemClock.elapsedRealtimeNanos())
        val slice = sensorRecorder.challengeSlice(challenge.startRelativeNs, endRelativeNs)
        require(slice.samples.isNotEmpty()) { "No challenge sensor samples were recorded." }
        return ChallengeSubmitRequest(
            nonce = challenge.issue.nonce,
            idempotencyKey = challenge.idempotencyKey,
            sensorWindow = ChallengeSensorWindow(
                startRelativeNs = challenge.startRelativeNs,
                endRelativeNs = endRelativeNs,
            ),
            samples = slice.samples,
            sensorSummary = slice.summary,
        )
    }

    private suspend fun preserveChallengeEvidence(
        capture: ActiveCapture,
        challenge: ActiveChallenge,
        request: ChallengeSubmitRequest,
    ) {
        val file = File(capture.directory, "challenge_${challenge.issue.challengeId}.json")
        val root = JSONObject().apply {
            put("challengeId", challenge.issue.challengeId)
            put("nonce", challenge.issue.nonce)
            put("idempotencyKey", request.idempotencyKey)
            put("sensorWindow", JSONObject().apply {
                put("startRelativeNs", request.sensorWindow.startRelativeNs)
                put("endRelativeNs", request.sensorWindow.endRelativeNs)
            })
            put("samples", JSONArray().apply {
                request.samples.forEach { sample ->
                    put(JSONObject().apply {
                        put("type", sample.type)
                        put("relativeTimestampNs", sample.relativeTimestampNs)
                        put("values", JSONArray(sample.values))
                        sample.accuracy?.let { put("accuracy", it) }
                    })
                }
            })
        }
        file.writeText(root.toString(), Charsets.UTF_8)
        repository.preserveChallengeEvidence(
            challenge.issue.challengeId,
            file.absolutePath,
        )
    }

    suspend fun stop(): EvidencePackage {
        val capture = checkNotNull(active) { "No capture is active." }
        check(activeChallenge == null) { "Current challenge must finish before capture stops." }
        try {
            val cameraResult = cameraManager.stopRecording()
            val sensorCounts = sensorRecorder.stop()
            val locations = locationRecorder.stopCapture()
            val durationMs =
                (cameraResult.videoEndMonotonicNs - cameraResult.videoStartMonotonicNs) / 1_000_000L
            require(durationMs >= 8_000L) { "Capture must be at least 8 seconds." }
            require(durationMs <= 60_000L) { "Capture exceeded the 60 second maximum." }
            require(locations.isNotEmpty()) { "No GPS samples were recorded during capture." }
            val locationSummary = locationRecorder.writePackage(
                File(capture.directory, "locations.json.gz"),
                locations,
            )
            val complete = com.siteproof.app.verification.model.CaptureCompleteRequest(
                captureDurationMs = durationMs,
                sensorSummary = sensorCounts.toApi(),
                locationSummary = locationSummary,
            )
            val evidence = packager.packageEvidence(
                directory = capture.directory,
                sessionId = capture.prepared.session.sessionId,
                inspection = capture.prepared.inspection,
                captureStartedAt = capture.captureStartedAt,
                captureEndedAt = Instant.now(),
                captureStartMonotonicNs = capture.captureStartNs,
                videoStartMonotonicNs = cameraResult.videoStartMonotonicNs,
                capabilities = capture.prepared.capabilities,
                captureComplete = complete,
                challenges = challengeTimeline.toList(),
            )
            repository.captureComplete(capture.prepared.session.sessionId, complete)
            repository.savePending(capture.prepared.inspection.id, capture.prepared.session.sessionId, evidence)
            repository.clearChallengeState(capture.prepared.session.sessionId)
            EvidenceUploadWorker.enqueue(context, capture.prepared.session.sessionId)
            return evidence
        } catch (error: Exception) {
            repository.abort(capture.prepared.session.sessionId, "UNKNOWN")
            throw error
        } finally {
            active = null
            sensorRecorder.stop()
            locationRecorder.stopCapture()
        }
    }

    suspend fun abort(reason: String) {
        val capture = active ?: return
        cameraManager.abortRecording()
        sensorRecorder.stop()
        locationRecorder.stopCapture()
        capture.directory.deleteRecursively()
        active = null
        activeChallenge = null
        pendingSubmission = null
        repository.abort(capture.prepared.session.sessionId, reason)
    }

    fun release() {
        cleanupCapture()
        cameraManager.release()
    }

    private fun cleanupCapture() {
        cameraManager.abortRecording()
        sensorRecorder.stop()
        locationRecorder.stopCapture()
        active = null
        activeChallenge = null
        pendingSubmission = null
    }
}
