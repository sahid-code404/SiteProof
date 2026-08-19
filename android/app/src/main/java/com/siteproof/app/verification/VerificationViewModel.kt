package com.siteproof.app.verification

import android.os.SystemClock
import androidx.camera.view.PreviewView
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.siteproof.app.verification.model.ChallengeIssue
import com.siteproof.app.verification.model.ChallengeValidationResult
import java.time.Duration
import java.time.Instant
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
    data class ChallengeLoading(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val elapsedMs: Long,
    ) : VerificationUiState
    data class ChallengeActive(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val challenge: ChallengeIssue,
        val remainingMs: Long,
        val elapsedMs: Long,
        val feedback: String,
    ) : VerificationUiState
    data class ChallengeChecking(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val challenge: ChallengeIssue,
        val elapsedMs: Long,
    ) : VerificationUiState
    data class ChallengeNetworkWait(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val challenge: ChallengeIssue,
        val elapsedMs: Long,
        val message: String,
    ) : VerificationUiState
    data class ChallengeResultState(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val result: ChallengeValidationResult,
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
    private var captureLimitJob: Job? = null
    private var challengeJob: Job? = null
    private var uploadJob: Job? = null

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
                val ready = _state.value as? VerificationUiState.Ready
                if (ready != null) coordinator.abandonPrepared(ready.prepared, "CAMERA_ERROR")
                _state.value = VerificationUiState.Error(error.message ?: "Camera is unavailable.")
            }
        }
    }

    fun cancelPrepared(onComplete: () -> Unit) {
        val ready = _state.value as? VerificationUiState.Ready
        if (ready == null) {
            onComplete()
            return
        }
        _state.value = VerificationUiState.Preparing
        viewModelScope.launch {
            coordinator.abandonPrepared(ready.prepared)
            onComplete()
        }
    }

    fun startCapture() {
        val ready = _state.value as? VerificationUiState.Ready ?: return
        viewModelScope.launch {
            try {
                coordinator.start(ready.prepared)
                startCaptureLimitGuard(ready.prepared)
                issueNextChallenge(ready.prepared)
            } catch (error: Exception) {
                _state.value = VerificationUiState.Error(error.message ?: "Unable to start live capture.")
            }
        }
    }

    private fun startCaptureLimitGuard(prepared: VerificationCaptureCoordinator.Prepared) {
        captureLimitJob?.cancel()
        captureLimitJob = viewModelScope.launch {
            while (true) {
                val elapsed = coordinator.captureElapsedMs()
                if (elapsed >= 59_500L) {
                    challengeJob?.cancel()
                    coordinator.abort("TIMEOUT")
                    _state.value = VerificationUiState.Error(
                        "Live verification reached the capture time limit before the challenge sequence finished.",
                    )
                    break
                }
                val current = _state.value
                _state.value = when (current) {
                    is VerificationUiState.ChallengeLoading -> current.copy(elapsedMs = elapsed)
                    is VerificationUiState.ChallengeActive -> current.copy(elapsedMs = elapsed)
                    is VerificationUiState.ChallengeChecking -> current.copy(elapsedMs = elapsed)
                    is VerificationUiState.ChallengeNetworkWait -> current.copy(elapsedMs = elapsed)
                    is VerificationUiState.ChallengeResultState -> current.copy(elapsedMs = elapsed)
                    else -> current
                }
                delay(250)
            }
        }
    }

    private suspend fun issueNextChallenge(prepared: VerificationCaptureCoordinator.Prepared) {
        _state.value = VerificationUiState.ChallengeLoading(prepared, coordinator.captureElapsedMs())
        try {
            val challenge = coordinator.beginNextChallenge()
            runChallengeWindow(prepared, challenge)
        } catch (error: Exception) {
            _state.value = VerificationUiState.ChallengeNetworkWait(
                prepared = prepared,
                challenge = placeholderChallenge(),
                elapsedMs = coordinator.captureElapsedMs(),
                message = "Connection is required to receive the next unpredictable challenge.",
            )
        }
    }

    private fun runChallengeWindow(
        prepared: VerificationCaptureCoordinator.Prepared,
        challenge: ChallengeIssue,
    ) {
        challengeJob?.cancel()
        challengeJob = viewModelScope.launch {
            val serverRemaining = runCatching {
                Duration.between(
                    Instant.parse(challenge.serverTime),
                    Instant.parse(challenge.expiresAt),
                ).toMillis()
            }.getOrDefault(15_000L).coerceIn(1_000L, 20_000L)
            val localDeadline = SystemClock.elapsedRealtime() + serverRemaining
            val baselineEnd = SystemClock.elapsedRealtime() + 600L
            var movementSeenAt: Long? = null

            while (true) {
                val now = SystemClock.elapsedRealtime()
                val remaining = (localDeadline - now).coerceAtLeast(0L)
                val feedback = when {
                    now < baselineEnd -> "Hold still for a moment…"
                    movementSeenAt != null -> "Movement detected… hold steady."
                    else -> "Perform the requested movement now."
                }
                _state.value = VerificationUiState.ChallengeActive(
                    prepared = prepared,
                    challenge = challenge,
                    remainingMs = remaining,
                    elapsedMs = coordinator.captureElapsedMs(),
                    feedback = feedback,
                )

                if (now >= baselineEnd && movementSeenAt == null && coordinator.movementDetected()) {
                    movementSeenAt = now
                }
                val settledEnough = movementSeenAt?.let { now - it >= 1_800L } == true
                if (settledEnough || remaining <= 1_200L) break
                delay(100)
            }
            submitCurrentChallenge(prepared, challenge)
        }
    }

    private suspend fun submitCurrentChallenge(
        prepared: VerificationCaptureCoordinator.Prepared,
        challenge: ChallengeIssue,
    ) {
        _state.value = VerificationUiState.ChallengeChecking(
            prepared,
            challenge,
            coordinator.captureElapsedMs(),
        )
        try {
            handleChallengeResult(prepared, coordinator.submitCurrentChallenge())
        } catch (error: Exception) {
            _state.value = VerificationUiState.ChallengeNetworkWait(
                prepared = prepared,
                challenge = challenge,
                elapsedMs = coordinator.captureElapsedMs(),
                message = "Connection lost. Your current challenge evidence has been saved. Reconnect to continue verification.",
            )
        }
    }

    fun retryChallengeConnection() {
        val waiting = _state.value as? VerificationUiState.ChallengeNetworkWait ?: return
        challengeJob?.cancel()
        challengeJob = viewModelScope.launch {
            if (waiting.challenge.challengeId.isBlank()) {
                issueNextChallenge(waiting.prepared)
                return@launch
            }
            _state.value = VerificationUiState.ChallengeChecking(
                waiting.prepared,
                waiting.challenge,
                coordinator.captureElapsedMs(),
            )
            try {
                handleChallengeResult(waiting.prepared, coordinator.retryCurrentChallengeSubmission())
            } catch (error: Exception) {
                _state.value = waiting.copy(
                    elapsedMs = coordinator.captureElapsedMs(),
                    message = "Still offline. Challenge evidence remains saved on this device.",
                )
            }
        }
    }

    private suspend fun handleChallengeResult(
        prepared: VerificationCaptureCoordinator.Prepared,
        result: ChallengeValidationResult,
    ) {
        _state.value = VerificationUiState.ChallengeResultState(
            prepared,
            result,
            coordinator.captureElapsedMs(),
        )
        delay(900)
        if (result.sequenceComplete) {
            finishAfterChallenges(prepared)
        } else {
            issueNextChallenge(prepared)
        }
    }

    private suspend fun finishAfterChallenges(prepared: VerificationCaptureCoordinator.Prepared) {
        captureLimitJob?.cancel()
        val remainingMinimum = (8_000L - coordinator.captureElapsedMs()).coerceAtLeast(0L)
        if (remainingMinimum > 0) delay(remainingMinimum)
        _state.value = VerificationUiState.Captured(
            prepared.session.sessionId,
            "PACKAGING",
            "Finalizing secure evidence and challenge timeline…",
        )
        try {
            coordinator.stop()
            monitorUpload(prepared.session.sessionId)
        } catch (error: Exception) {
            _state.value = VerificationUiState.Error(
                error.message ?: "Unable to finalize challenge evidence.",
                canRetry = false,
            )
        }
    }

    fun abortForInterruption() {
        if (!isLiveState(_state.value)) return
        challengeJob?.cancel()
        captureLimitJob?.cancel()
        viewModelScope.launch {
            coordinator.abort("APP_INTERRUPTED")
            _state.value = VerificationUiState.Error(
                "Live proof was interrupted and this session was aborted. Start a new verification.",
            )
        }
    }

    fun abortByUser() {
        if (!isLiveState(_state.value)) return
        challengeJob?.cancel()
        captureLimitJob?.cancel()
        viewModelScope.launch {
            coordinator.abort("USER_CANCELLED")
            _state.value = VerificationUiState.Error("Verification aborted. Start a new live verification.")
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
                    "UPLOADED" -> "Evidence submitted successfully. Challenge results are available; final authenticity is not yet calculated." to "UPLOADED"
                    "UPLOADING" -> "Uploading video, sensor, location and challenge timeline evidence…" to "UPLOADING"
                    "FAILED" -> "Upload interrupted. Evidence is safely stored on this device and will retry when connected." to "FAILED"
                    else -> "Capture saved securely. Waiting for connection to upload." to pending.uploadStatus
                }
                _state.value = VerificationUiState.Captured(sessionId, status, message)
            }
        }
    }

    private fun isLiveState(value: VerificationUiState): Boolean = when (value) {
        is VerificationUiState.ChallengeLoading,
        is VerificationUiState.ChallengeActive,
        is VerificationUiState.ChallengeChecking,
        is VerificationUiState.ChallengeNetworkWait,
        is VerificationUiState.ChallengeResultState,
        -> true
        else -> false
    }

    private fun placeholderChallenge() = ChallengeIssue(
        challengeId = "",
        sequenceNumber = 0,
        attemptNumber = 0,
        totalChallenges = 3,
        type = "",
        instruction = "Waiting for server challenge",
        parameters = com.siteproof.app.verification.model.ChallengeParameters(0.0, 0.0, 0.0),
        issuedAt = Instant.now().toString(),
        expiresAt = Instant.now().plusSeconds(15).toString(),
        serverTime = Instant.now().toString(),
        nonce = "",
    )

    override fun onCleared() {
        captureLimitJob?.cancel()
        challengeJob?.cancel()
        uploadJob?.cancel()
        coordinator.release()
        super.onCleared()
    }
}
