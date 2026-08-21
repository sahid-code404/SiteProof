package com.siteproof.app.verification.upload

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
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
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody
import okio.BufferedSink
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
        val network = currentNetworkLabel()

        return try {
            val captureComplete = readCaptureComplete(File(directory, "metadata.json"))
            api.captureComplete(sessionId, captureComplete)

            val descriptors = descriptors(directory)
            val totalBytes = descriptors.sumOf { it.sizeBytes }.coerceAtLeast(1L)
            dao.updateUploadProgress(
                sessionId,
                "UPLOADING",
                0,
                0L,
                totalBytes,
                network,
                System.currentTimeMillis(),
            )
            val initiated = api.initiateEvidence(
                sessionId,
                EvidenceInitiateRequest(pending.uploadIdempotencyKey, descriptors),
            )
            val byType = descriptors.associateBy { it.type }
            var completedBytes = 0L
            initiated.targets.forEach { target ->
                val descriptor = requireNotNull(byType[target.type])
                if (target.alreadyUploaded) {
                    completedBytes += descriptor.sizeBytes
                    publishProgress(sessionId, completedBytes, totalBytes, network)
                    return@forEach
                }
                val file = File(directory, descriptor.filename)
                val baseBytes = completedBytes
                var lastPercent = -1
                val progressBody = ProgressRequestBody(
                    file = file,
                    mediaType = descriptor.mimeType.toMediaType(),
                ) { fileBytes ->
                    val uploaded = (baseBytes + fileBytes).coerceAtMost(totalBytes)
                    val percent = ((uploaded * 100L) / totalBytes).toInt().coerceIn(0, 100)
                    if (percent != lastPercent) {
                        lastPercent = percent
                        CoroutineScope(coroutineContext).launch {
                            dao.updateUploadProgress(
                                sessionId,
                                "UPLOADING",
                                percent,
                                uploaded,
                                totalBytes,
                                network,
                                System.currentTimeMillis(),
                            )
                        }
                    }
                }
                api.uploadEvidence(target.uploadPath, progressBody)
                completedBytes += descriptor.sizeBytes
                publishProgress(sessionId, completedBytes, totalBytes, network)
            }
            api.completeEvidence(sessionId, EvidenceCompleteRequest(pending.manifestSha256))
            dao.updateUploadProgress(
                sessionId,
                "UPLOADED",
                100,
                totalBytes,
                totalBytes,
                network,
                System.currentTimeMillis(),
            )
            directory.deleteRecursively()
            dao.markUploaded(sessionId)
            Result.success()
        } catch (error: HttpException) {
            dao.updateUploadStatus(sessionId, "FAILED", System.currentTimeMillis())
            if (UploadRetryPolicy.shouldRetry(error.code())) Result.retry() else Result.failure()
        } catch (error: IOException) {
            dao.updateUploadStatus(sessionId, "FAILED", System.currentTimeMillis())
            Result.retry()
        } catch (error: Exception) {
            dao.updateUploadStatus(sessionId, "FAILED", System.currentTimeMillis())
            Result.failure()
        }
    }

    private suspend fun publishProgress(sessionId: String, uploaded: Long, total: Long, network: String?) {
        val percent = ((uploaded * 100L) / total.coerceAtLeast(1L)).toInt().coerceIn(0, 100)
        PendingEvidenceDatabase.get(applicationContext).pendingEvidenceDao().updateUploadProgress(
            sessionId,
            "UPLOADING",
            percent,
            uploaded,
            total,
            network,
            System.currentTimeMillis(),
        )
    }

    private fun currentNetworkLabel(): String? {
        val manager = applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return null
        val network = manager.activeNetwork ?: return null
        val capabilities = manager.getNetworkCapabilities(network) ?: return null
        return when {
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "Wi-Fi"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "mobile data"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "Ethernet"
            else -> "connected network"
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

private class ProgressRequestBody(
    private val file: File,
    private val mediaType: MediaType,
    private val onProgress: (Long) -> Unit,
) : RequestBody() {
    override fun contentType(): MediaType = mediaType

    override fun contentLength(): Long = file.length()

    override fun writeTo(sink: BufferedSink) {
        file.inputStream().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            var uploaded = 0L
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                sink.write(buffer, 0, read)
                uploaded += read
                onProgress(uploaded)
            }
        }
    }
}
