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
        val videoEndMonotonicNs: Long,
        val recordedDurationNs: Long,
        val fileSizeBytes: Long,
    )

    private var provider: ProcessCameraProvider? = null
    private var previewUseCase: Preview? = null
    private var boundPreviewView: PreviewView? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var recording: Recording? = null
    private var completion: CompletableDeferred<RecordingResult>? = null
    private var startCompletion: CompletableDeferred<Long>? = null
    private var startNs: Long = 0L

    suspend fun bind(previewView: PreviewView, lifecycleOwner: LifecycleOwner) {
        val existingPreview = previewUseCase
        if (provider != null && videoCapture != null && existingPreview != null) {
            if (boundPreviewView === previewView) return

            if (recording != null) {
                // Evidence recording has priority over UI recovery. Never swap Preview surface
                // providers while Recorder is active: some CameraX/device combinations stall the
                // shared camera graph for hundreds of milliseconds or more during that change.
                // The persistent-overlay UI should make this path unnecessary, but keeping this
                // guard prevents a future Compose refactor from damaging the encoded evidence.
                return
            }

            existingPreview.surfaceProvider = previewView.surfaceProvider
            boundPreviewView = previewView
            return
        }

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
        previewUseCase = preview
        boundPreviewView = previewView
        videoCapture = capture
    }

    suspend fun startRecording(outputFile: File): Long {
        check(recording == null) { "A recording is already active." }
        val capture = checkNotNull(videoCapture) { "Camera preview is not ready." }
        outputFile.parentFile?.mkdirs()
        val result = CompletableDeferred<RecordingResult>()
        val started = CompletableDeferred<Long>()
        completion = result
        startCompletion = started
        startNs = 0L
        recording = capture.output
            .prepareRecording(context, FileOutputOptions.Builder(outputFile).build())
            .start(ContextCompat.getMainExecutor(context)) { event ->
                when (event) {
                    is VideoRecordEvent.Start -> {
                        // Anchor the wall-clock video interval only when CameraX confirms that
                        // recording has actually started.
                        val monotonicStartNs = SystemClock.elapsedRealtimeNanos()
                        startNs = monotonicStartNs
                        if (!started.isCompleted) {
                            started.complete(monotonicStartNs)
                        }
                    }

                    is VideoRecordEvent.Finalize -> {
                        val activeCompletion = completion ?: return@start
                        val recordedDurationNs = event.recordingStats.recordedDurationNanos
                        val finalizedAtNs = SystemClock.elapsedRealtimeNanos()
                        val effectiveStartNs = if (startNs > 0L) {
                            startNs
                        } else {
                            (finalizedAtNs - recordedDurationNs).coerceAtLeast(0L)
                        }
                        if (event.hasError()) {
                            val error = IllegalStateException(
                                "Camera recording failed with code ${event.error}.",
                            )
                            if (!started.isCompleted) {
                                started.completeExceptionally(error)
                            }
                            activeCompletion.completeExceptionally(error)
                        } else {
                            if (!started.isCompleted) {
                                started.complete(effectiveStartNs)
                            }
                            activeCompletion.complete(
                                RecordingResult(
                                    videoStartMonotonicNs = effectiveStartNs,
                                    // Keep the real Finalize callback time as the wall-clock end
                                    // anchor. CameraX's encoded duration is stored separately and
                                    // remains authoritative for MP4 duration validation.
                                    videoEndMonotonicNs = finalizedAtNs,
                                    recordedDurationNs = recordedDurationNs,
                                    fileSizeBytes = outputFile.length(),
                                ),
                            )
                        }
                        recording = null
                        startCompletion = null
                    }
                }
            }

        // Do not expose an active verification until CameraX confirms recording began.
        return started.await()
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
        startCompletion?.cancel()
        startCompletion = null
        completion?.cancel()
        completion = null
    }

    fun release() {
        abortRecording()
        provider?.unbindAll()
        provider = null
        previewUseCase = null
        boundPreviewView = null
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
