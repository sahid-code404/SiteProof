package com.siteproof.app.verification.upload

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.siteproof.app.data.TokenStore
import com.siteproof.app.data.createApi
import com.siteproof.app.verification.db.PendingEvidenceDatabase
import com.siteproof.app.verification.evidence.EvidenceHasher
import com.siteproof.app.verification.model.CaptureCompleteRequest
import com.siteproof.app.verification.model.EvidenceCompleteRequest
import com.siteproof.app.verification.model.EvidenceFileDescriptor
import com.siteproof.app.verification.model.EvidenceInitiateRequest
import com.siteproof.app.verification.model.LocationSummary
import com.siteproof.app.verification.model.SensorSummary
import java.io.File
import java.util.concurrent.TimeUnit
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.asRequestBody
import org.json.JSONObject
import retrofit2.HttpException

class EvidenceUploadWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val sessionId = inputData.getString(KEY_SESSION_ID) ?: return Result.failure()
        val database = PendingEvidenceDatabase.get(applicationContext)
        val dao = database.pendingEvidenceDao()
        val pending = dao.get(sessionId) ?: return Result.success()
        if (pending.uploadStatus == "UPLOADED") return Result.success()
        val directory = File(pending.localEvidencePath)
        if (!directory.isDirectory) {
            dao.updateUploadStatus(sessionId, "FAILED", System.currentTimeMillis())
            return Result.failure()
        }
        val tokenStore = TokenStore(applicationContext)
        if (tokenStore.accessToken.isNullOrBlank()) return Result.failure()
        val api = createApi(applicationContext, tokenStore)
        dao.updateUploadStatus(sessionId, "UPLOADING", System.currentTimeMillis())

        return try {
            val captureComplete = readCaptureComplete(File(directory, "metadata.json"))
            api.captureComplete(sessionId, captureComplete)

            val descriptors = descriptors(directory)
            val initiated = api.initiateEvidence(
                sessionId,
                EvidenceInitiateRequest(pending.uploadIdempotencyKey, descriptors),
            )
            val byType = descriptors.associateBy { it.type }
            initiated.targets.forEach { target ->
                if (target.alreadyUploaded) return@forEach
                val descriptor = requireNotNull(byType[target.type])
                val file = File(directory, descriptor.filename)
                api.uploadEvidence(
                    target.uploadPath,
                    file.asRequestBody(descriptor.mimeType.toMediaType()),
                )
            }
            api.completeEvidence(sessionId, EvidenceCompleteRequest(pending.manifestSha256))
            directory.deleteRecursively()
            dao.markUploaded(sessionId)
            Result.success()
        } catch (error: HttpException) {
            dao.updateUploadStatus(sessionId, "FAILED", System.currentTimeMillis())
            if (UploadRetryPolicy.shouldRetry(error.code())) Result.retry() else Result.failure()
        } catch (error: Exception) {
            dao.updateUploadStatus(sessionId, "FAILED", System.currentTimeMillis())
            Result.retry()
        }
    }

    private fun descriptors(directory: File): List<EvidenceFileDescriptor> = listOf(
        descriptor("VIDEO", File(directory, "capture.mp4"), "video/mp4"),
        descriptor("SENSOR_DATA", File(directory, "sensors.ndjson.gz"), "application/octet-stream"),
        descriptor("LOCATION_DATA", File(directory, "locations.json.gz"), "application/gzip"),
        descriptor("SESSION_METADATA", File(directory, "metadata.json"), "application/json"),
        descriptor("MANIFEST", File(directory, "manifest.json"), "application/json"),
    )

    private fun descriptor(type: String, file: File, mime: String): EvidenceFileDescriptor {
        require(file.isFile && file.length() > 0) { "$type evidence is missing." }
        return EvidenceFileDescriptor(type, file.name, file.length(), EvidenceHasher.sha256(file), mime)
    }

    private fun readCaptureComplete(metadataFile: File): CaptureCompleteRequest {
        val root = JSONObject(metadataFile.readText())
        val capture = root.getJSONObject("capture")
        val sensors = root.getJSONObject("sensorSummary")
        val locations = root.getJSONObject("locationSummary")
        return CaptureCompleteRequest(
            captureDurationMs = capture.getLong("durationMs"),
            sensorSummary = SensorSummary(
                accelerometerSamples = sensors.getInt("accelerometerSamples"),
                gyroscopeSamples = sensors.getInt("gyroscopeSamples"),
                rotationVectorSamples = sensors.getInt("rotationVectorSamples"),
                magnetometerSamples = sensors.optInt("magnetometerSamples", 0),
            ),
            locationSummary = LocationSummary(
                locationSamples = locations.getInt("locationSamples"),
                bestAccuracyMeters = locations.optDoubleOrNull("bestAccuracyMeters"),
                firstRelativeTimestampNs = locations.optLongOrNull("firstRelativeTimestampNs"),
                lastRelativeTimestampNs = locations.optLongOrNull("lastRelativeTimestampNs"),
            ),
        )
    }

    private fun JSONObject.optDoubleOrNull(name: String): Double? =
        if (has(name) && !isNull(name)) getDouble(name) else null

    private fun JSONObject.optLongOrNull(name: String): Long? =
        if (has(name) && !isNull(name)) getLong(name) else null

    companion object {
        private const val KEY_SESSION_ID = "session_id"

        fun enqueue(context: Context, sessionId: String) {
            val request = OneTimeWorkRequestBuilder<EvidenceUploadWorker>()
                .setInputData(workDataOf(KEY_SESSION_ID to sessionId))
                .setConstraints(
                    Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build(),
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                "siteproof-upload-$sessionId",
                ExistingWorkPolicy.KEEP,
                request,
            )
        }
    }
}
