package com.siteproof.app.verification

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.view.WindowManager
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.siteproof.app.verification.model.ChallengeValidationResult
import kotlin.math.ceil
import kotlin.math.roundToInt

private val RecordingRed = Color(0xFFFF5147)
private val RecoveryAmber = Color(0xFFFFA62B)

@Composable
fun VerificationScreen(
    viewModel: VerificationViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val activity = context as? Activity
    var showAbortDialog by remember { mutableStateOf(false) }
    val live = isLiveState(state)

    DisposableEffect(activity) {
        activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        onDispose { activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE) }
    }

    DisposableEffect(lifecycleOwner, live) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP && live) viewModel.abortForInterruption()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
        val cameraGranted = grants[Manifest.permission.CAMERA] == true ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        val locationGranted = grants[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (cameraGranted && locationGranted) viewModel.permissionsGranted()
    }

    fun requestPermissions() = launcher.launch(
        arrayOf(
            Manifest.permission.CAMERA,
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION,
        ),
    )

    BackHandler(enabled = state is VerificationUiState.Ready) { viewModel.cancelPrepared(onBack) }
    BackHandler(enabled = live) { showAbortDialog = true }

    if (showAbortDialog) {
        AlertDialog(
            onDismissRequest = { showAbortDialog = false },
            shape = RoundedCornerShape(26.dp),
            title = { Text("Stop verification?") },
            text = { Text("The current live capture will be discarded. You can restart verification from the inspection.") },
            confirmButton = {
                TextButton(onClick = { showAbortDialog = false; viewModel.abortByUser() }) { Text("Stop capture") }
            },
            dismissButton = {
                TextButton(onClick = { showAbortDialog = false }) { Text("Keep recording") }
            },
        )
    }

    Scaffold(containerColor = MaterialTheme.colorScheme.background) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            val current = state
            val prepared = cameraPrepared(current)

            if (prepared != null) {
                key(prepared.session.sessionId) {
                    PersistentCameraHost(
                        state = current,
                        prepared = prepared,
                        lifecycleOwner = lifecycleOwner,
                        bindCamera = viewModel::bindCamera,
                        onStart = viewModel::startCapture,
                        onBack = { viewModel.cancelPrepared(onBack) },
                        retryConnection = viewModel::retryChallengeConnection,
                        retryChallenge = viewModel::retryChallenge,
                        onAbort = { showAbortDialog = true },
                    )
                }
            } else {
                when (current) {
                    VerificationUiState.PermissionIntro -> PermissionIntro(onBack, ::requestPermissions)
                    VerificationUiState.Preparing -> Loading("Preparing secure capture…")
                    is VerificationUiState.Captured -> CaptureResult(current, viewModel::retryUpload, onBack)
                    is VerificationUiState.Error -> ErrorState(
                        message = current.message,
                        canRetry = current.canRetry,
                        retry = viewModel::retryVerification,
                        onBack = onBack,
                    )
                    else -> Unit
                }
            }
        }
    }
}

private fun cameraPrepared(state: VerificationUiState): VerificationCaptureCoordinator.Prepared? = when (state) {
    is VerificationUiState.Ready -> state.prepared
    is VerificationUiState.ChallengeLoading -> state.prepared
    is VerificationUiState.ChallengeActive -> state.prepared
    is VerificationUiState.ChallengeChecking -> state.prepared
    is VerificationUiState.ChallengeNetworkWait -> state.prepared
    is VerificationUiState.ChallengeResultState -> state.prepared
    is VerificationUiState.CaptureFinishing -> state.prepared
    else -> null
}

private fun liveElapsedMs(state: VerificationUiState): Long? = when (state) {
    is VerificationUiState.ChallengeLoading -> state.elapsedMs
    is VerificationUiState.ChallengeActive -> state.elapsedMs
    is VerificationUiState.ChallengeChecking -> state.elapsedMs
    is VerificationUiState.ChallengeNetworkWait -> state.elapsedMs
    is VerificationUiState.ChallengeResultState -> state.elapsedMs
    is VerificationUiState.CaptureFinishing -> state.elapsedMs
    else -> null
}

private fun requiredRemainingMs(state: VerificationUiState, requiredSeconds: Int): Long? {
    if (state is VerificationUiState.CaptureFinishing) return state.remainingMs
    val elapsed = liveElapsedMs(state) ?: return null
    return (requiredSeconds * 1_000L - elapsed).coerceAtLeast(0L)
}

private fun secondsLabel(milliseconds: Long): String = "${ceil(milliseconds / 1000.0).toInt()}s"

private fun durationLabel(seconds: Int): String = when {
    seconds >= 60 && seconds % 60 == 0 -> "${seconds / 60} min"
    seconds >= 60 -> "${seconds / 60} min ${seconds % 60} sec"
    else -> "$seconds sec"
}

@Composable
private fun PersistentCameraHost(
    state: VerificationUiState,
    prepared: VerificationCaptureCoordinator.Prepared,
    lifecycleOwner: LifecycleOwner,
    bindCamera: (PreviewView, LifecycleOwner) -> Unit,
    onStart: () -> Unit,
    onBack: () -> Unit,
    retryConnection: () -> Unit,
    retryChallenge: () -> Unit,
    onAbort: () -> Unit,
) {
    Box(Modifier.fillMaxSize().background(Color.Black)) {
        CameraPreview(
            lifecycleOwner = lifecycleOwner,
            bindCamera = bindCamera,
            modifier = Modifier.fillMaxSize(),
        )

        val recordingRemaining = requiredRemainingMs(state, prepared.inspection.captureDurationSeconds)
        CaptureHeader(
            title = prepared.inspection.title,
            isRecording = state !is VerificationUiState.Ready,
            recordingRemaining = recordingRemaining,
        )

        when (state) {
            is VerificationUiState.Ready -> ReadyOverlay(prepared, onStart, onBack)
            is VerificationUiState.ChallengeLoading -> LiveLoadingOverlay("Getting the next movement…", onAbort)
            is VerificationUiState.ChallengeActive -> ChallengeActiveOverlay(state, onAbort)
            is VerificationUiState.ChallengeChecking -> LiveLoadingOverlay("Checking that movement…", onAbort)
            is VerificationUiState.ChallengeNetworkWait -> NetworkWaitOverlay(state, retryConnection, onAbort)
            is VerificationUiState.ChallengeResultState -> ChallengeResultOverlay(state.result, retryChallenge, onAbort)
            is VerificationUiState.CaptureFinishing -> CaptureFinishingOverlay(state, onAbort)
            else -> Unit
        }
    }
}

@Composable
private fun BoxScope.CaptureHeader(
    title: String,
    isRecording: Boolean,
    recordingRemaining: Long?,
) {
    GlassPanel(
        modifier = Modifier
            .align(Alignment.TopCenter)
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 10.dp),
        alpha = 0.74f,
        radius = 20,
    ) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (isRecording) {
                Box(
                    Modifier
                        .size(9.dp)
                        .background(RecordingRed, CircleShape),
                )
            }
            Column(Modifier.weight(1f)) {
                Text(
                    if (isRecording) "LIVE EVIDENCE" else "READY TO VERIFY",
                    style = MaterialTheme.typography.labelLarge,
                    color = if (isRecording) RecordingRed else MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    title,
                    style = MaterialTheme.typography.titleMedium,
                    color = Color.White,
                    maxLines = 1,
                )
            }
            if (isRecording && recordingRemaining != null) {
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = Color.Black.copy(alpha = 0.28f),
                    border = BorderStroke(1.dp, Color.White.copy(alpha = 0.12f)),
                ) {
                    Text(
                        if (recordingRemaining > 0L) secondsLabel(recordingRemaining) else "MIN ✓",
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                        color = Color.White,
                        style = MaterialTheme.typography.labelLarge,
                    )
                }
            }
        }
    }
}

@Composable
private fun PermissionIntro(onBack: () -> Unit, onContinue: () -> Unit) {
    Box(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(20.dp),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            shape = RoundedCornerShape(28.dp),
            color = MaterialTheme.colorScheme.surface,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
            shadowElevation = 8.dp,
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                Text("Live verification", style = MaterialTheme.typography.headlineMedium)
                Text(
                    "SiteProof records evidence and sensor context together so the result can be independently reviewed.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                PermissionLine("Camera", "Records the assigned site while movement checks are shown on top of the live view.")
                PermissionLine("Location", "Confirms capture starts within the assigned site radius.")
                PermissionLine("Motion sensors", "Measures only the requested phone movement during verification.")
                Spacer(Modifier.height(2.dp))
                Button(onClick = onContinue, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text("Allow and continue") }
                TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Not now") }
            }
        }
    }
}

@Composable
private fun PermissionLine(title: String, body: String) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.56f),
    ) {
        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun BoxScope.ReadyOverlay(
    prepared: VerificationCaptureCoordinator.Prepared,
    onStart: () -> Unit,
    onBack: () -> Unit,
) {
    val sensorsReady = prepared.capabilities.accelerometer && prepared.capabilities.gyroscope
    GlassPanel(
        modifier = Modifier
            .align(Alignment.BottomCenter)
            .fillMaxWidth()
            .padding(12.dp),
        alpha = 0.86f,
    ) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Capture check", style = MaterialTheme.typography.titleLarge, color = Color.White)
            StatusRow("Location", "${prepared.location.accuracyLabel} · ±${prepared.location.location.accuracyMeters.roundToInt()} m")
            StatusRow("Site distance", "${prepared.location.distanceMeters.roundToInt()} m of ${prepared.inspection.allowedRadiusMeters} m")
            StatusRow("Motion sensors", if (sensorsReady) "Ready" else "Limited")
            StatusRow("Required video", "${durationLabel(prepared.inspection.captureDurationSeconds)} minimum")
            Text(
                "The camera stays recording while challenge animations appear over the live preview.",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.7f),
            )
            Button(onClick = onStart, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text("Start live verification") }
            TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) {
                Text("Back", color = Color.White.copy(alpha = 0.82f))
            }
        }
    }
}

@Composable
private fun BoxScope.ChallengeActiveOverlay(
    state: VerificationUiState.ChallengeActive,
    onAbort: () -> Unit,
) {
    GlassPanel(
        modifier = Modifier
            .align(Alignment.BottomCenter)
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 12.dp),
        alpha = 0.78f,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 13.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    "MOVEMENT CHECK",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    "${state.challenge.sequenceNumber}/${state.challenge.totalChallenges}",
                    style = MaterialTheme.typography.labelLarge,
                    color = Color.White.copy(alpha = 0.74f),
                )
            }
            ChallengeMovementGuide(state.challenge, state.guidance)
            Text(
                state.feedback,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 2.dp),
            )
            Text(
                "${secondsLabel(state.remainingMs)} remaining · keep the site in frame",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.68f),
                modifier = Modifier.padding(top = 3.dp),
            )
            TextButton(onClick = onAbort) { Text("Stop capture", color = Color.White.copy(alpha = 0.72f)) }
        }
    }
}

@Composable
private fun BoxScope.LiveLoadingOverlay(message: String, onAbort: () -> Unit) {
    GlassPanel(
        modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(12.dp),
        alpha = 0.78f,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(18.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            CircularProgressIndicator(modifier = Modifier.size(34.dp), strokeWidth = 3.dp)
            Text(message, color = Color.White, textAlign = TextAlign.Center, modifier = Modifier.padding(10.dp))
            Text(
                "Recording continues in the background.",
                color = Color.White.copy(alpha = 0.65f),
                style = MaterialTheme.typography.bodySmall,
            )
            TextButton(onClick = onAbort) { Text("Stop capture", color = Color.White.copy(alpha = 0.72f)) }
        }
    }
}

@Composable
private fun BoxScope.NetworkWaitOverlay(
    state: VerificationUiState.ChallengeNetworkWait,
    retry: () -> Unit,
    onAbort: () -> Unit,
) {
    GlassPanel(
        modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(12.dp),
        alpha = 0.84f,
        borderColor = RecoveryAmber.copy(alpha = 0.42f),
    ) {
        Column(
            Modifier.fillMaxWidth().padding(18.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Connection interrupted", style = MaterialTheme.typography.titleLarge, color = RecoveryAmber)
            Text(state.message, color = Color.White, textAlign = TextAlign.Center, modifier = Modifier.padding(vertical = 8.dp))
            Text(
                "Your evidence recording is still active. Reconnect and continue without restarting the capture.",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.68f),
                textAlign = TextAlign.Center,
            )
            Button(onClick = retry, modifier = Modifier.fillMaxWidth().padding(top = 14.dp)) { Text("Reconnect") }
            TextButton(onClick = onAbort) { Text("Stop capture", color = Color.White.copy(alpha = 0.72f)) }
        }
    }
}

@Composable
private fun BoxScope.ChallengeResultOverlay(
    result: ChallengeValidationResult,
    retryChallenge: () -> Unit,
    onAbort: () -> Unit,
) {
    val passed = result.result == "PASS"
    val title = when {
        passed -> "Movement verified"
        result.result == "FAIL" -> "Movement not verified"
        else -> "Movement was inconclusive"
    }
    val detail = when {
        passed -> "Nice. The next movement will appear automatically while recording continues."
        result.retryAllowed -> "Your recording is safe. Retry this step with a fresh movement challenge."
        else -> "This step cannot be retried. Stop the capture and restart verification from the inspection."
    }

    GlassPanel(
        modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(12.dp),
        alpha = 0.82f,
        borderColor = if (passed) MaterialTheme.colorScheme.primary.copy(alpha = 0.35f) else MaterialTheme.colorScheme.error.copy(alpha = 0.4f),
    ) {
        Column(
            Modifier.fillMaxWidth().padding(18.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleLarge,
                color = if (passed) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                textAlign = TextAlign.Center,
            )
            Text(detail, color = Color.White.copy(alpha = 0.76f), textAlign = TextAlign.Center, modifier = Modifier.padding(8.dp))
            if (!passed && result.retryAllowed) {
                Button(onClick = retryChallenge, modifier = Modifier.fillMaxWidth().padding(top = 6.dp)) { Text("Retry challenge") }
            }
            TextButton(onClick = onAbort) { Text("Stop capture", color = Color.White.copy(alpha = 0.72f)) }
        }
    }
}

@Composable
private fun BoxScope.CaptureFinishingOverlay(
    state: VerificationUiState.CaptureFinishing,
    onAbort: () -> Unit,
) {
    val requiredMs = state.prepared.inspection.captureDurationSeconds * 1_000f
    val progress = (state.elapsedMs / requiredMs).coerceIn(0f, 1f)
    GlassPanel(
        modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(12.dp),
        alpha = 0.82f,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(18.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Movement checks complete", style = MaterialTheme.typography.titleLarge, color = Color.White, textAlign = TextAlign.Center)
            if (state.remainingMs > 0L) {
                Text(
                    "Keep the site steady in frame · ${secondsLabel(state.remainingMs)} minimum recording remaining",
                    textAlign = TextAlign.Center,
                    color = Color.White.copy(alpha = 0.72f),
                )
            } else {
                Text("Minimum recording reached. Sealing the evidence package…", color = Color.White.copy(alpha = 0.72f), textAlign = TextAlign.Center)
            }
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth(),
                color = MaterialTheme.colorScheme.primary,
                trackColor = Color.White.copy(alpha = 0.15f),
            )
            TextButton(onClick = onAbort) { Text("Stop capture", color = Color.White.copy(alpha = 0.72f)) }
        }
    }
}

private fun isLiveState(state: VerificationUiState): Boolean = when (state) {
    is VerificationUiState.ChallengeLoading,
    is VerificationUiState.ChallengeActive,
    is VerificationUiState.ChallengeChecking,
    is VerificationUiState.ChallengeNetworkWait,
    is VerificationUiState.ChallengeResultState,
    is VerificationUiState.CaptureFinishing,
    -> true
    else -> false
}

@Composable
private fun CameraPreview(
    lifecycleOwner: LifecycleOwner,
    bindCamera: (PreviewView, LifecycleOwner) -> Unit,
    modifier: Modifier,
) {
    AndroidView(
        modifier = modifier,
        factory = { context ->
            PreviewView(context).apply {
                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                scaleType = PreviewView.ScaleType.FILL_CENTER
            }.also { bindCamera(it, lifecycleOwner) }
        },
    )
}

@Composable
private fun CaptureResult(state: VerificationUiState.Captured, retry: (String) -> Unit, onBack: () -> Unit) {
    Box(Modifier.fillMaxSize().padding(20.dp), contentAlignment = Alignment.Center) {
        Surface(
            shape = RoundedCornerShape(28.dp),
            color = MaterialTheme.colorScheme.surface,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
            shadowElevation = 8.dp,
        ) {
            Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Evidence saved", style = MaterialTheme.typography.headlineMedium)
                Text(state.message, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (state.uploadStatus == "FAILED") {
                    Surface(
                        shape = RoundedCornerShape(14.dp),
                        color = MaterialTheme.colorScheme.errorContainer,
                    ) {
                        Text(
                            "Upload failed, but the evidence remains queued safely on this device.",
                            modifier = Modifier.padding(12.dp),
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                    }
                    Button(onClick = { retry(state.sessionId) }, modifier = Modifier.fillMaxWidth()) { Text("Retry upload") }
                }
                if (state.uploadStatus == "UPLOADED") {
                    Button(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Done") }
                }
            }
        }
    }
}

@Composable
private fun ErrorState(message: String, canRetry: Boolean, retry: () -> Unit, onBack: () -> Unit) {
    val friendly = friendlyError(message)
    Box(Modifier.fillMaxSize().padding(20.dp), contentAlignment = Alignment.Center) {
        Surface(
            shape = RoundedCornerShape(28.dp),
            color = MaterialTheme.colorScheme.surface,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.2f)),
            shadowElevation = 8.dp,
        ) {
            Column(
                Modifier.fillMaxWidth().padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Surface(
                    modifier = Modifier.size(54.dp),
                    shape = CircleShape,
                    color = MaterialTheme.colorScheme.errorContainer,
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text("!", style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.onErrorContainer, fontWeight = FontWeight.Bold)
                    }
                }
                Text(friendly.first, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
                Text(friendly.second, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
                Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
                if (canRetry) Button(onClick = retry, modifier = Modifier.fillMaxWidth()) { Text("Try again") }
                TextButton(onClick = onBack) { Text("Back to inspection") }
            }
        }
    }
}

private fun friendlyError(message: String): Pair<String, String> {
    val normalized = message.lowercase()
    return when {
        "permission" in normalized || "camera" in normalized && "denied" in normalized ->
            "Camera access is needed" to "Allow camera and location access, then retry verification."
        "location" in normalized || "gps" in normalized ->
            "Location could not be confirmed" to "Move to an open area, enable location services and try again."
        "sensor" in normalized || "gyro" in normalized || "accelerometer" in normalized ->
            "Motion sensing is unavailable" to "Keep the phone steady and retry. If this continues, this device may not support the required challenge."
        "network" in normalized || "connection" in normalized || "timeout" in normalized ->
            "Connection unavailable" to "Check your connection. Captured evidence is retained whenever the workflow can safely retry."
        else -> "Verification could not continue" to "Nothing has been submitted incorrectly. Retry the step or return to the inspection."
    }
}

@Composable
private fun Loading(message: String) {
    Column(
        Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator()
        Text(message, modifier = Modifier.padding(20.dp), textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun StatusRow(label: String, value: String) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 3.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, color = Color.White.copy(alpha = 0.66f))
        Text(value, color = Color.White, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun GlassPanel(
    modifier: Modifier,
    alpha: Float,
    radius: Int = 26,
    borderColor: Color = Color.White.copy(alpha = 0.14f),
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(radius.dp),
        color = Color(0xFF101114).copy(alpha = alpha),
        border = BorderStroke(1.dp, borderColor),
        shadowElevation = 8.dp,
        content = content,
    )
}
