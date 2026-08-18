package com.siteproof.app.verification

import android.os.SystemClock
import androidx.camera.view.PreviewView
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.siteproof.app.verification.upload.EvidenceUploadWorker
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface VerificationUiState {
    data object PermissionIntro : VerificationUiState
    data object Preparing : VerificationUiState
    data class Ready(val prepared: VerificationCaptureCoordinator.Prepared) : VerificationUiState
    data class Capturing(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val elapsedMs: Long,
    ) : VerificationUiState
    data class Captured(
        val sessionId: String,
        val uploadStatus: String,
        val message: String,
    ) : VerificationUiState
    data class Error(val message: String, val canRetry: Boolean = true) : VerificationUiState
}

class VerificationViewModel(
    private val inspectionId: String,
    private val coordinator: VerificationCaptureCoordinator,
    private val repository: VerificationRepository,
    private val enqueueUpload: (String) -> Unit,
) : ViewModel() {
    private val _state = MutableStateFlow<VerificationUiState>(VerificationUiState.PermissionIntro)
    val state: StateFlow<VerificationUiState> = _state.asStateFlow()
    private var timerJob: Job? = null
    private var uploadJob: Job? = null
    private var captureStartedNs: Long = 0L

    fun permissionsGranted() {
        if (_state.value !is VerificationUiState.PermissionIntro && _state.value !is VerificationUiState.Error) return
        prepare()
    }

    fun prepare() {
        viewModelScope.launch {
            _state.value = VerificationUiState.Preparing
            _state.value = try {
                VerificationUiState.Ready(coordinator.prepare(inspectionId))
            } catch (error: Exception) {
                VerificationUiState.Error(error.message ?: "Unable to prepare live verification.")
            }
        }
    }

    fun bindCamera(previewView: PreviewView, lifecycleOwner: LifecycleOwner) {
        viewModelScope.launch {
            try {
                coordinator.bindCamera(previewView, lifecycleOwner)
            } catch (error: Exception) {
                _state.value = VerificationUiState.Error(error.message ?: "Camera is unavailable.")
            }
        }
    }

    fun startCapture() {
        val ready = _state.value as? VerificationUiState.Ready ?: return
        viewModelScope.launch {
            try {
                coordinator.start(ready.prepared)
                captureStartedNs = SystemClock.elapsedRealtimeNanos()
                _state.value = VerificationUiState.Capturing(ready.prepared, 0L)
                timerJob?.cancel()
                timerJob = launch {
                    while (true) {
                        val current = _state.value as? VerificationUiState.Capturing ?: break
                        val elapsed = (SystemClock.elapsedRealtimeNanos() - captureStartedNs) / 1_000_000L
                        _state.value = current.copy(elapsedMs = elapsed)
                        delay(250)
                    }
                }
            } catch (error: Exception) {
                _state.value = VerificationUiState.Error(error.message ?: "Unable to start live capture.")
            }
        }
    }

    fun stopCapture() {
        val capturing = _state.value as? VerificationUiState.Capturing ?: return
        if (capturing.elapsedMs < 8_000L) return
        timerJob?.cancel()
        viewModelScope.launch {
            _state.value = VerificationUiState.Captured(
                capturing.prepared.session.sessionId,
                "PACKAGING",
                "Finalizing secure evidence…",
            )
            try {
                coordinator.stop()
                monitorUpload(capturing.prepared.session.sessionId)
            } catch (error: Exception) {
                _state.value = VerificationUiState.Error(error.message ?: "Unable to finalize evidence.", canRetry = false)
            }
        }
    }

    fun abortForInterruption() {
        if (_state.value !is VerificationUiState.Capturing) return
        timerJob?.cancel()
        viewModelScope.launch {
            coordinator.abort("APP_INTERRUPTED")
            _state.value = VerificationUiState.Error(
                "Capture was interrupted and this session was aborted. Start a new live verification.",
            )
        }
    }

    fun abortByUser() {
        if (_state.value !is VerificationUiState.Capturing) return
        timerJob?.cancel()
        viewModelScope.launch {
            coordinator.abort("USER_CANCELLED")
            _state.value = VerificationUiState.Error("Capture aborted. Start a new live verification.")
        }
    }

    fun retryUpload(sessionId: String) {
        enqueueUpload(sessionId)
        monitorUpload(sessionId)
    }

    private fun monitorUpload(sessionId: String) {
        uploadJob?.cancel()
        uploadJob = viewModelScope.launch {
            repository.observePending(sessionId).collect { pending ->
                if (pending == null) return@collect
                val (message, status) = when (pending.uploadStatus) {
                    "UPLOADED" -> "Evidence submitted successfully. Awaiting verification analysis." to "UPLOADED"
                    "UPLOADING" -> "Uploading evidence securely…" to "UPLOADING"
                    "FAILED" -> "Upload interrupted. Evidence is safely stored on this device and will retry when connected." to "FAILED"
                    else -> "Capture saved securely. Waiting for connection to upload." to pending.uploadStatus
                }
                _state.value = VerificationUiState.Captured(sessionId, status, message)
            }
        }
    }

    override fun onCleared() {
        timerJob?.cancel()
        uploadJob?.cancel()
        coordinator.release()
        super.onCleared()
    }
}
