package com.siteproof.app.verification

import android.os.SystemClock
import androidx.camera.view.PreviewView
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.siteproof.app.verification.model.ChallengeIssue
import com.siteproof.app.verification.model.ChallengeValidationResult
import com.siteproof.app.verification.model.SemanticChallengeCompleteResult
import com.siteproof.app.verification.model.SemanticChallengeIssue
import com.siteproof.app.verification.sensors.ChallengeGuidanceStatus
import com.siteproof.app.verification.sensors.ChallengeMovementGuidance
import java.io.IOException
import java.time.Duration
import java.time.Instant
import java.util.Locale
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
    data class StartingCapture(val prepared: VerificationCaptureCoordinator.Prepared) : VerificationUiState
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
        val guidance: ChallengeMovementGuidance = ChallengeMovementGuidance(),
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
    data class SemanticChallengeLoading(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val elapsedMs: Long,
    ) : VerificationUiState
    data class SemanticChallengeActive(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val challenge: SemanticChallengeIssue,
        val remainingMs: Long,
        val elapsedMs: Long,
        val canComplete: Boolean,
    ) : VerificationUiState
    data class SemanticChallengeChecking(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val challenge: SemanticChallengeIssue,
        val elapsedMs: Long,
    ) : VerificationUiState
    data class SemanticChallengeNetworkWait(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val challenge: SemanticChallengeIssue?,
        val elapsedMs: Long,
        val message: String,
    ) : VerificationUiState
    data class SemanticChallengeResultState(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val result: SemanticChallengeCompleteResult,
        val elapsedMs: Long,
    ) : VerificationUiState
    data class CaptureFinishing(
        val prepared: VerificationCaptureCoordinator.Prepared,
        val remainingMs: Long,
        val elapsedMs: Long,
    ) : VerificationUiState
    data class Captured(
        val sessionId: String,
        val uploadStatus: String,
        val message: String,
        val progressPercent: Int? = null,
        val uploadedBytes: Long = 0L,
        val totalBytes: Long = 0L,
        val networkLabel: String? = null,
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
    private var startJob: Job? = null
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

    fun retryVerification() {
        startJob?.cancel()
        challengeJob?.cancel()
        captureLimitJob?.cancel()
        uploadJob?.cancel()
        viewModelScope.launch {
            runCatching { coordinator.abort("RETRY_REQUESTED") }
            _state.value = VerificationUiState.Preparing
            _state.value = try {
                VerificationUiState.Ready(coordinator.prepare(inspectionId))
            } catch (error: Exception) {
                VerificationUiState.Error(error.message ?: "Unable to start a new verification.")
            }
        }
    }

    fun bindCamera(previewView: PreviewView, lifecycleOwner: LifecycleOwner) {
        viewModelScope.launch {
            try {
                coordinator.bindCamera(previewView, lifecycleOwner)
            } catch (error: Exception) {
                val prepared = preparedFromState(_state.value)
                if (prepared != null) coordinator.abandonPrepared(prepared, "CAMERA_ERROR")
                _state.value = VerificationUiState.Error(error.message ?: "Camera is unavailable.")
            }
        }
    }

    fun cancelPrepared(onComplete: () -> Unit) {
        val prepared = preparedFromState(_state.value)
        if (prepared == null || isLiveState(_state.value)) {
            onComplete()
            return
        }
        _state.value = VerificationUiState.Preparing
        viewModelScope.launch {
            coordinator.abandonPrepared(prepared)
            onComplete()
        }
    }

    fun startCapture() {
        val ready = _state.value as? VerificationUiState.Ready ?: return
        _state.value = VerificationUiState.StartingCapture(ready.prepared)
        startJob?.cancel()
        startJob = viewModelScope.launch {
            try {
                coordinator.start(ready.prepared)
                startCaptureLimitGuard(ready.prepared)
                issueNextChallenge(ready.prepared)
            } catch (error: Exception) {
                runCatching { coordinator.abandonPrepared(ready.prepared, "UNKNOWN") }
                _state.value = VerificationUiState.Error(error.message ?: "Unable to start live capture.")
            }
        }
    }

    private fun startCaptureLimitGuard(prepared: VerificationCaptureCoordinator.Prepared) {
        captureLimitJob?.cancel()
        captureLimitJob = viewModelScope.launch {
            val technicalLimitMs = prepared.session.captureMaximumSeconds * 1_000L
            while (true) {
                val wallElapsed = coordinator.captureElapsedMs()
                if (wallElapsed >= technicalLimitMs) {
                    challengeJob?.cancel()
                    coordinator.abort("TIMEOUT")
                    _state.value = VerificationUiState.Error(
                        "Live verification reached its server-authorized safety time limit before the proof sequence finished.",
                    )
                    break
                }
                val encodedElapsed = coordinator.videoElapsedMs()
                val current = _state.value
                _state.value = when (current) {
                    is VerificationUiState.ChallengeLoading -> current.copy(elapsedMs = encodedElapsed)
                    is VerificationUiState.ChallengeActive -> current.copy(elapsedMs = encodedElapsed)
                    is VerificationUiState.ChallengeChecking -> current.copy(elapsedMs = encodedElapsed)
                    is VerificationUiState.ChallengeNetworkWait -> current.copy(elapsedMs = encodedElapsed)
                    is VerificationUiState.ChallengeResultState -> current.copy(elapsedMs = encodedElapsed)
                    is VerificationUiState.SemanticChallengeLoading -> current.copy(elapsedMs = encodedElapsed)
                    is VerificationUiState.SemanticChallengeActive -> current.copy(elapsedMs = encodedElapsed)
                    is VerificationUiState.SemanticChallengeChecking -> current.copy(elapsedMs = encodedElapsed)
                    is VerificationUiState.SemanticChallengeNetworkWait -> current.copy(elapsedMs = encodedElapsed)
                    is VerificationUiState.SemanticChallengeResultState -> current.copy(elapsedMs = encodedElapsed)
                    else -> current
                }
                delay(250)
            }
        }
    }

    private suspend fun issueNextChallenge(prepared: VerificationCaptureCoordinator.Prepared) {
        _state.value = VerificationUiState.ChallengeLoading(prepared, coordinator.videoElapsedMs())
        try {
            val challenge = coordinator.beginNextChallenge()
            runChallengeWindow(prepared, challenge)
        } catch (error: Exception) {
            if (error is IOException) {
                _state.value = VerificationUiState.ChallengeNetworkWait(
                    prepared = prepared,
                    challenge = placeholderChallenge(),
                    elapsedMs = coordinator.videoElapsedMs(),
                    message = "Connection is required to receive the next unpredictable movement challenge.",
                )
            } else {
                failChallengeProtocol(
                    error,
                    "The server could not start the next movement challenge. This live proof was aborted for safety.",
                )
            }
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
            }.getOrDefault(18_000L).coerceIn(1_000L, 20_000L)
            val localDeadline = SystemClock.elapsedRealtime() + serverRemaining
            val baselineEnd = SystemClock.elapsedRealtime() + 600L
            var goodRangeSeenAt: Long? = null

            while (true) {
                val now = SystemClock.elapsedRealtime()
                val remaining = (localDeadline - now).coerceAtLeast(0L)
                val guidance = coordinator.challengeGuidance(challenge)
                val feedback = when {
                    now < baselineEnd -> "Hold still for a moment…"
                    guidance.status == ChallengeGuidanceStatus.WRONG_DIRECTION ->
                        "Wrong direction — follow the animated arrow."
                    guidance.status == ChallengeGuidanceStatus.GOOD_RANGE ->
                        "Good range — hold the phone steady."
                    guidance.status == ChallengeGuidanceStatus.TOO_FAR ->
                        "Too far — move back slightly into the target range."
                    guidance.status == ChallengeGuidanceStatus.TOO_LITTLE && guidance.signedDegrees > 5.0 ->
                        "Keep going — follow the guide."
                    guidance.status == ChallengeGuidanceStatus.TOO_LITTLE ->
                        "Start moving in the shown direction."
                    else -> "Start moving in the shown direction."
                }
                _state.value = VerificationUiState.ChallengeActive(
                    prepared = prepared,
                    challenge = challenge,
                    remainingMs = remaining,
                    elapsedMs = coordinator.videoElapsedMs(),
                    feedback = feedback,
                    guidance = guidance,
                )

                if (now >= baselineEnd && guidance.status == ChallengeGuidanceStatus.GOOD_RANGE) {
                    if (goodRangeSeenAt == null) goodRangeSeenAt = now
                } else {
                    goodRangeSeenAt = null
                }
                val targetHeld = goodRangeSeenAt?.let { now - it >= 500L } == true
                if (targetHeld || remaining <= 1_200L) break
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
            coordinator.videoElapsedMs(),
        )
        try {
            handleChallengeResult(prepared, coordinator.submitCurrentChallenge())
        } catch (error: Exception) {
            if (error is IOException) {
                _state.value = VerificationUiState.ChallengeNetworkWait(
                    prepared = prepared,
                    challenge = challenge,
                    elapsedMs = coordinator.videoElapsedMs(),
                    message = "Connection lost. Your current movement evidence has been saved. Reconnect to continue verification.",
                )
            } else {
                failChallengeProtocol(
                    error,
                    "Movement evidence was rejected by the server. This live proof was aborted rather than reusing stale evidence.",
                )
            }
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
                coordinator.videoElapsedMs(),
            )
            try {
                handleChallengeResult(waiting.prepared, coordinator.retryCurrentChallengeSubmission())
            } catch (error: Exception) {
                if (error is IOException) {
                    _state.value = waiting.copy(
                        elapsedMs = coordinator.videoElapsedMs(),
                        message = "Still offline. Movement evidence remains saved on this device.",
                    )
                } else {
                    failChallengeProtocol(
                        error,
                        "The saved movement can no longer be accepted by the server. Start a new live verification.",
                    )
                }
            }
        }
    }

    fun retryChallenge() {
        val current = _state.value as? VerificationUiState.ChallengeResultState ?: return
        if (!current.result.retryAllowed || current.result.result == "PASS") return
        challengeJob?.cancel()
        challengeJob = viewModelScope.launch { issueNextChallenge(current.prepared) }
    }

    private suspend fun handleChallengeResult(
        prepared: VerificationCaptureCoordinator.Prepared,
        result: ChallengeValidationResult,
    ) {
        _state.value = VerificationUiState.ChallengeResultState(
            prepared,
            result,
            coordinator.videoElapsedMs(),
        )
        if (result.sequenceComplete) {
            delay(700)
            if (prepared.session.semanticChallengeCount > 0) {
                issueNextSemanticChallenge(prepared)
            } else {
                finishAfterChallenges(prepared)
            }
            return
        }
        if (result.result != "PASS" && result.retryAllowed) return
        delay(800)
        issueNextChallenge(prepared)
    }

    private suspend fun issueNextSemanticChallenge(prepared: VerificationCaptureCoordinator.Prepared) {
        _state.value = VerificationUiState.SemanticChallengeLoading(
            prepared,
            coordinator.videoElapsedMs(),
        )
        try {
            val challenge = coordinator.beginNextSemanticChallenge()
            runSemanticChallengeWindow(prepared, challenge)
        } catch (error: Exception) {
            if (error is IOException) {
                _state.value = VerificationUiState.SemanticChallengeNetworkWait(
                    prepared = prepared,
                    challenge = null,
                    elapsedMs = coordinator.videoElapsedMs(),
                    message = "Connection is required to receive the next unpredictable visual proof instruction.",
                )
            } else {
                failChallengeProtocol(
                    error,
                    "The server could not start the next visual proof challenge. This live proof was aborted for safety.",
                )
            }
        }
    }

    private fun runSemanticChallengeWindow(
        prepared: VerificationCaptureCoordinator.Prepared,
        challenge: SemanticChallengeIssue,
    ) {
        challengeJob?.cancel()
        challengeJob = viewModelScope.launch {
            val serverRemaining = runCatching {
                Duration.between(
                    Instant.parse(challenge.serverTime),
                    Instant.parse(challenge.expiresAt),
                ).toMillis()
            }.getOrDefault(25_000L).coerceIn(2_000L, 60_000L)
            val localDeadline = SystemClock.elapsedRealtime() + serverRemaining
            while (true) {
                val now = SystemClock.elapsedRealtime()
                val remaining = (localDeadline - now).coerceAtLeast(0L)
                val proofElapsed = coordinator.semanticChallengeElapsedMs()
                _state.value = VerificationUiState.SemanticChallengeActive(
                    prepared = prepared,
                    challenge = challenge,
                    remainingMs = remaining,
                    elapsedMs = coordinator.videoElapsedMs(),
                    canComplete = proofElapsed >= SEMANTIC_CLIENT_MINIMUM_MS,
                )
                if (remaining <= 0L) {
                    failChallengeProtocol(
                        IllegalStateException("Visual proof challenge expired before it was completed."),
                        "The visual proof challenge expired. Start a new verification.",
                    )
                    return@launch
                }
                delay(100)
            }
        }
    }

    fun completeSemanticChallenge() {
        val current = _state.value as? VerificationUiState.SemanticChallengeActive ?: return
        if (!current.canComplete) return
        challengeJob?.cancel()
        challengeJob = viewModelScope.launch {
            _state.value = VerificationUiState.SemanticChallengeChecking(
                current.prepared,
                current.challenge,
                coordinator.videoElapsedMs(),
            )
            try {
                handleSemanticChallengeResult(
                    current.prepared,
                    coordinator.completeCurrentSemanticChallenge(),
                )
            } catch (error: Exception) {
                if (error is IOException) {
                    _state.value = VerificationUiState.SemanticChallengeNetworkWait(
                        prepared = current.prepared,
                        challenge = current.challenge,
                        elapsedMs = coordinator.videoElapsedMs(),
                        message = "Connection lost while sealing this visual proof window. Reconnect to continue without re-recording it.",
                    )
                } else {
                    failChallengeProtocol(
                        error,
                        "The visual proof window could not be accepted by the server. This capture was aborted for safety.",
                    )
                }
            }
        }
    }

    fun retrySemanticChallengeConnection() {
        val waiting = _state.value as? VerificationUiState.SemanticChallengeNetworkWait ?: return
        challengeJob?.cancel()
        challengeJob = viewModelScope.launch {
            if (waiting.challenge == null) {
                issueNextSemanticChallenge(waiting.prepared)
                return@launch
            }
            _state.value = VerificationUiState.SemanticChallengeChecking(
                waiting.prepared,
                waiting.challenge,
                coordinator.videoElapsedMs(),
            )
            try {
                handleSemanticChallengeResult(
                    waiting.prepared,
                    coordinator.retryCurrentSemanticCompletion(),
                )
            } catch (error: Exception) {
                if (error is IOException) {
                    _state.value = waiting.copy(
                        elapsedMs = coordinator.videoElapsedMs(),
                        message = "Still offline. The visual proof completion remains pending on this device.",
                    )
                } else {
                    failChallengeProtocol(
                        error,
                        "The pending visual proof can no longer be accepted. Start a new live verification.",
                    )
                }
            }
        }
    }

    private suspend fun handleSemanticChallengeResult(
        prepared: VerificationCaptureCoordinator.Prepared,
        result: SemanticChallengeCompleteResult,
    ) {
        _state.value = VerificationUiState.SemanticChallengeResultState(
            prepared,
            result,
            coordinator.videoElapsedMs(),
        )
        delay(650)
        if (result.sequenceComplete) {
            finishAfterChallenges(prepared)
        } else {
            issueNextSemanticChallenge(prepared)
        }
    }

    private suspend fun failChallengeProtocol(error: Exception, fallback: String) {
        captureLimitJob?.cancel()
        coordinator.abort("UNKNOWN")
        val detail = error.message?.takeIf { it.isNotBlank() }
        _state.value = VerificationUiState.Error(
            message = if (detail == null) fallback else "$fallback\n\n$detail",
            canRetry = true,
        )
    }

    private suspend fun finishAfterChallenges(prepared: VerificationCaptureCoordinator.Prepared) {
        captureLimitJob?.cancel()
        val requiredSeconds = prepared.session.requiredCaptureDurationSeconds
        while (true) {
            val remaining = coordinator.videoRemainingMs(requiredSeconds)
            _state.value = VerificationUiState.CaptureFinishing(
                prepared = prepared,
                remainingMs = remaining,
                elapsedMs = coordinator.videoElapsedMs(),
            )
            if (remaining <= 0L) break
            delay(minOf(250L, remaining.coerceAtLeast(50L)))
        }

        try {
            coordinator.stop()
            _state.value = VerificationUiState.Captured(
                prepared.session.sessionId,
                "PACKAGING",
                "Secure evidence finalized. Preparing upload…",
            )
            monitorUpload(prepared.session.sessionId)
        } catch (error: Exception) {
            _state.value = VerificationUiState.Error(
                error.message ?: "Unable to finalize challenge evidence.",
                canRetry = true,
            )
        }
    }

    fun abortForInterruption() {
        val current = _state.value
        if (!isLiveState(current)) return
        startJob?.cancel()
        challengeJob?.cancel()
        captureLimitJob?.cancel()
        viewModelScope.launch {
            val prepared = preparedFromState(current)
            if (current is VerificationUiState.StartingCapture && prepared != null) {
                coordinator.abandonPrepared(prepared, "APP_INTERRUPTED")
            } else {
                coordinator.abort("APP_INTERRUPTED")
            }
            _state.value = VerificationUiState.Error(
                "Live proof was interrupted and this session was aborted. Start a new verification.",
                canRetry = true,
            )
        }
    }

    fun abortByUser() {
        val current = _state.value
        if (!isLiveState(current)) return
        startJob?.cancel()
        challengeJob?.cancel()
        captureLimitJob?.cancel()
        viewModelScope.launch {
            val prepared = preparedFromState(current)
            if (current is VerificationUiState.StartingCapture && prepared != null) {
                coordinator.abandonPrepared(prepared, "USER_CANCELLED")
            } else {
                coordinator.abort("USER_CANCELLED")
            }
            _state.value = VerificationUiState.Error(
                "Verification aborted. Start a new live verification.",
                canRetry = true,
            )
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
                val network = pending.networkLabel?.let { " over $it" }.orEmpty()
                val progressText = if (pending.totalBytes > 0L) {
                    "${pending.uploadProgressPercent}% · ${formatBytes(pending.uploadedBytes)} of ${formatBytes(pending.totalBytes)}"
                } else {
                    null
                }
                val (message, status) = when (pending.uploadStatus) {
                    "UPLOADED" -> "Evidence submitted successfully. Challenge results are available; final authenticity is not yet calculated." to "UPLOADED"
                    "UPLOADING" -> "Uploading$network${progressText?.let { " · $it" }.orEmpty()}" to "UPLOADING"
                    "FAILED" -> "Upload interrupted. Evidence is safely stored on this device. Automatic retry remains enabled, or retry now." to "FAILED"
                    else -> "Capture saved securely. Waiting for a connected network to upload." to pending.uploadStatus
                }
                _state.value = VerificationUiState.Captured(
                    sessionId = sessionId,
                    uploadStatus = status,
                    message = message,
                    progressPercent = if (pending.totalBytes > 0L) pending.uploadProgressPercent else null,
                    uploadedBytes = pending.uploadedBytes,
                    totalBytes = pending.totalBytes,
                    networkLabel = pending.networkLabel,
                )
            }
        }
    }

    private fun formatBytes(value: Long): String {
        val mb = value / (1024.0 * 1024.0)
        return String.format(Locale.US, "%.1f MB", mb)
    }

    private fun isLiveState(value: VerificationUiState): Boolean = when (value) {
        is VerificationUiState.StartingCapture,
        is VerificationUiState.ChallengeLoading,
        is VerificationUiState.ChallengeActive,
        is VerificationUiState.ChallengeChecking,
        is VerificationUiState.ChallengeNetworkWait,
        is VerificationUiState.ChallengeResultState,
        is VerificationUiState.SemanticChallengeLoading,
        is VerificationUiState.SemanticChallengeActive,
        is VerificationUiState.SemanticChallengeChecking,
        is VerificationUiState.SemanticChallengeNetworkWait,
        is VerificationUiState.SemanticChallengeResultState,
        is VerificationUiState.CaptureFinishing,
        -> true
        else -> false
    }

    private fun preparedFromState(value: VerificationUiState): VerificationCaptureCoordinator.Prepared? = when (value) {
        is VerificationUiState.Ready -> value.prepared
        is VerificationUiState.StartingCapture -> value.prepared
        is VerificationUiState.ChallengeLoading -> value.prepared
        is VerificationUiState.ChallengeActive -> value.prepared
        is VerificationUiState.ChallengeChecking -> value.prepared
        is VerificationUiState.ChallengeNetworkWait -> value.prepared
        is VerificationUiState.ChallengeResultState -> value.prepared
        is VerificationUiState.SemanticChallengeLoading -> value.prepared
        is VerificationUiState.SemanticChallengeActive -> value.prepared
        is VerificationUiState.SemanticChallengeChecking -> value.prepared
        is VerificationUiState.SemanticChallengeNetworkWait -> value.prepared
        is VerificationUiState.SemanticChallengeResultState -> value.prepared
        is VerificationUiState.CaptureFinishing -> value.prepared
        else -> null
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
        expiresAt = Instant.now().plusSeconds(18).toString(),
        serverTime = Instant.now().toString(),
        nonce = "",
    )

    override fun onCleared() {
        startJob?.cancel()
        captureLimitJob?.cancel()
        challengeJob?.cancel()
        uploadJob?.cancel()
        coordinator.release()
        super.onCleared()
    }

    private companion object {
        const val SEMANTIC_CLIENT_MINIMUM_MS = 1_800L
    }
}
