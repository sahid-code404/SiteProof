package com.siteproof.app.verification

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.view.WindowManager
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
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
            title = { Text("Stop verification?") },
            text = { Text("This live capture will be discarded and you'll need to start again.") },
            confirmButton = {
                TextButton(onClick = { showAbortDialog = false; viewModel.abortByUser() }) { Text("Stop") }
            },
            dismissButton = {
                TextButton(onClick = { showAbortDialog = false }) { Text("Keep going") }
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
                    VerificationUiState.Preparing -> Loading("Preparing verification…")
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
    Box(Modifier.fillMaxSize()) {
        CameraPreview(
            lifecycleOwner = lifecycleOwner,
            bindCamera = bindCamera,
            modifier = Modifier.fillMaxSize(),
        )

        val recordingRemaining = requiredRemainingMs(state, prepared.inspection.captureDurationSeconds)
        Surface(
            modifier = Modifier.align(Alignment.TopCenter).fillMaxWidth(),
            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f),
            tonalElevation = 2.dp,
        ) {
            Column(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    if (state is VerificationUiState.Ready) {
                        "Ready to verify"
                    } else if (recordingRemaining != null && recordingRemaining > 0L) {
                        "Recording · ${secondsLabel(recordingRemaining)} minimum remaining"
                    } else {
                        "Recording · minimum reached"
                    },
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    prepared.inspection.title,
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.Center,
                )
            }
        }

        when (state) {
            is VerificationUiState.Ready -> ReadyOverlay(prepared, onStart, onBack)
            is VerificationUiState.ChallengeLoading -> LiveLoadingOverlay("Getting the next challenge…", onAbort)
            is VerificationUiState.ChallengeActive -> ChallengeActiveOverlay(state, onAbort)
            is VerificationUiState.ChallengeChecking -> LiveLoadingOverlay("Checking movement…", onAbort)
            is VerificationUiState.ChallengeNetworkWait -> NetworkWaitOverlay(state, retryConnection, onAbort)
            is VerificationUiState.ChallengeResultState -> ChallengeResultOverlay(state.result, retryChallenge, onAbort)
            is VerificationUiState.CaptureFinishing -> CaptureFinishingOverlay(state, onAbort)
            else -> Unit
        }
    }
}

@Composable
private fun PermissionIntro(onBack: () -> Unit, onContinue: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(horizontal = 24.dp, vertical = 32.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Verification", style = MaterialTheme.typography.headlineMedium)
        Text(
            "SiteProof needs camera and location access for a live site check.",
            modifier = Modifier.padding(top = 8.dp),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(Modifier.height(24.dp))
        PermissionLine("Camera", "Records the inspection while you complete the movement checks.")
        Spacer(Modifier.height(14.dp))
        PermissionLine("Location", "Confirms the capture starts near the assigned site.")
        Spacer(Modifier.height(14.dp))
        PermissionLine("Motion sensors", "Measures the requested phone movement.")

        Spacer(Modifier.height(28.dp))
        Button(onClick = onContinue, modifier = Modifier.fillMaxWidth().height(50.dp)) { Text("Continue") }
        TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Back") }
    }
}

@Composable
private fun PermissionLine(title: String, body: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun BoxScope.ReadyOverlay(
    prepared: VerificationCaptureCoordinator.Prepared,
    onStart: () -> Unit,
    onBack: () -> Unit,
) {
    val sensorsReady = prepared.capabilities.accelerometer && prepared.capabilities.gyroscope
    Surface(
        modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.95f),
        tonalElevation = 4.dp,
    ) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            StatusRow("Location", "${prepared.location.accuracyLabel} · ±${prepared.location.location.accuracyMeters.roundToInt()} m")
            StatusRow("Site distance", "${prepared.location.distanceMeters.roundToInt()} m of ${prepared.inspection.allowedRadiusMeters} m")
            StatusRow("Motion sensors", if (sensorsReady) "Ready" else "Limited")
            StatusRow("Required video", "${durationLabel(prepared.inspection.captureDurationSeconds)} minimum")
            Text(
                "The video will keep recording until this minimum is reached, even if the movement checks finish earlier.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(onClick = onStart, modifier = Modifier.fillMaxWidth().height(50.dp)) { Text("Start verification") }
            TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Back") }
        }
    }
}

@Composable
private fun BoxScope.ChallengeActiveOverlay(
    state: VerificationUiState.ChallengeActive,
    onAbort: () -> Unit,
) {
    Surface(
        modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.95f),
        tonalElevation = 4.dp,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                "Step ${state.challenge.sequenceNumber} of ${state.challenge.totalChallenges}",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
            )
            ChallengeMovementGuide(state.challenge, state.guidance)
            Text(
                state.feedback,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 4.dp),
            )
            Text(
                "Challenge window · ${secondsLabel(state.remainingMs)} remaining",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 2.dp),
            )
            TextButton(onClick = onAbort) { Text("Stop") }
        }
    }
}

@Composable
private fun BoxScope.LiveLoadingOverlay(message: String, onAbort: () -> Unit) {
    Surface(
        modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.95f),
        tonalElevation = 4.dp,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            CircularProgressIndicator()
            Text(message, textAlign = TextAlign.Center, modifier = Modifier.padding(10.dp))
            TextButton(onClick = onAbort) { Text("Stop") }
        }
    }
}

@Composable
private fun BoxScope.NetworkWaitOverlay(
    state: VerificationUiState.ChallengeNetworkWait,
    retry: () -> Unit,
    onAbort: () -> Unit,
) {
    Surface(
        modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f),
        tonalElevation = 4.dp,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Connection lost", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.error)
            Text(state.message, textAlign = TextAlign.Center, modifier = Modifier.padding(vertical = 8.dp))
            Text(
                "Recording stays active while you reconnect.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(onClick = retry, modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) { Text("Try again") }
            TextButton(onClick = onAbort) { Text("Stop") }
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
        passed -> "Step complete"
        result.result == "FAIL" -> "Movement not verified"
        else -> "Could not verify movement"
    }
    val detail = when {
        passed -> "Getting the next step…"
        result.retryAllowed -> "Try again with a new movement step."
        else -> "No retry is available for this step."
    }

    Surface(
        modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.95f),
        tonalElevation = 4.dp,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(title, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
            Text(detail, textAlign = TextAlign.Center, modifier = Modifier.padding(8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (!passed && result.retryAllowed) {
                Button(onClick = retryChallenge, modifier = Modifier.fillMaxWidth().padding(top = 6.dp)) { Text("Try again") }
            }
            TextButton(onClick = onAbort) { Text("Stop") }
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
    Surface(
        modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f),
        tonalElevation = 4.dp,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(18.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Movement checks complete", style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
            if (state.remainingMs > 0L) {
                Text(
                    "Keep the camera steady · ${secondsLabel(state.remainingMs)} recording remaining",
                    textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                Text("Minimum recording reached. Finalizing secure video…", textAlign = TextAlign.Center)
            }
            LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
            TextButton(onClick = onAbort) { Text("Stop") }
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
    Column(
        Modifier.fillMaxSize().padding(28.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Evidence saved", style = MaterialTheme.typography.headlineMedium)
        Text(state.message, modifier = Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (state.uploadStatus == "FAILED") {
            Button(onClick = { retry(state.sessionId) }, modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) { Text("Retry upload") }
        }
        if (state.uploadStatus == "UPLOADED") {
            Button(onClick = onBack, modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) { Text("Done") }
        }
    }
}

@Composable
private fun ErrorState(message: String, canRetry: Boolean, retry: () -> Unit, onBack: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.Center) {
        Text("Couldn't continue", style = MaterialTheme.typography.headlineMedium)
        Text(message, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 12.dp))
        if (canRetry) Button(onClick = retry, modifier = Modifier.fillMaxWidth()) { Text("Try again") }
        TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Back") }
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
        Text(message, modifier = Modifier.padding(20.dp), textAlign = TextAlign.Center)
    }
}

@Composable
private fun StatusRow(label: String, value: String) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 3.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value)
    }
}
