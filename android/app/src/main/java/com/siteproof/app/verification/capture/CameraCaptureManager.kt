package com.siteproof.app.verification.capture

import android.content.Context
import android.os.SystemClock
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import java.io.File
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.suspendCancellableCoroutine

class CameraCaptureManager(private val context: Context) {
    data class RecordingResult(
        val videoStartMonotonicNs: Long,
        val fileSizeBytes: Long,
    )

    private var provider: ProcessCameraProvider? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var recording: Recording? = null
    private var completion: CompletableDeferred<RecordingResult>? = null
    private var startNs: Long = 0L

    suspend fun bind(previewView: PreviewView, lifecycleOwner: LifecycleOwner) {
        val cameraProvider = awaitProvider()
        val preview = Preview.Builder().build().also { it.surfaceProvider = previewView.surfaceProvider }
        val qualitySelector = QualitySelector.fromOrderedList(
            listOf(Quality.FHD, Quality.HD, Quality.SD),
            FallbackStrategy.lowerQualityOrHigherThan(Quality.SD),
        )
        val recorder = Recorder.Builder().setQualitySelector(qualitySelector).build()
        val capture = VideoCapture.withOutput(recorder)
        cameraProvider.unbindAll()
        val selector = if (cameraProvider.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA)) {
            CameraSelector.DEFAULT_BACK_CAMERA
        } else {
            throw IllegalStateException("A rear camera is required for SiteProof infrastructure capture.")
        }
        cameraProvider.bindToLifecycle(lifecycleOwner, selector, preview, capture)
        provider = cameraProvider
        videoCapture = capture
    }

    fun startRecording(outputFile: File) {
        check(recording == null) { "A recording is already active." }
        val capture = checkNotNull(videoCapture) { "Camera preview is not ready." }
        outputFile.parentFile?.mkdirs()
        val result = CompletableDeferred<RecordingResult>()
        completion = result
        startNs = SystemClock.elapsedRealtimeNanos()
        recording = capture.output
            .prepareRecording(context, FileOutputOptions.Builder(outputFile).build())
            .start(ContextCompat.getMainExecutor(context)) { event ->
                if (event is VideoRecordEvent.Finalize) {
                    val activeCompletion = completion ?: return@start
                    if (event.hasError()) {
                        activeCompletion.completeExceptionally(
                            IllegalStateException("Camera recording failed with code ${event.error}."),
                        )
                    } else {
                        activeCompletion.complete(
                            RecordingResult(
                                videoStartMonotonicNs = startNs,
                                fileSizeBytes = outputFile.length(),
                            ),
                        )
                    }
                    recording = null
                }
            }
    }

    suspend fun stopRecording(): RecordingResult {
        val active = checkNotNull(recording) { "No camera recording is active." }
        val result = checkNotNull(completion)
        active.stop()
        return result.await().also { completion = null }
    }

    fun abortRecording() {
        recording?.close()
        recording = null
        completion?.cancel()
        completion = null
    }

    fun release() {
        abortRecording()
        provider?.unbindAll()
        provider = null
        videoCapture = null
    }

    private suspend fun awaitProvider(): ProcessCameraProvider = suspendCancellableCoroutine { continuation ->
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener(
            {
                try {
                    continuation.resume(future.get())
                } catch (error: Exception) {
                    continuation.resumeWithException(error)
                }
            },
            ContextCompat.getMainExecutor(context),
        )
    }
}
