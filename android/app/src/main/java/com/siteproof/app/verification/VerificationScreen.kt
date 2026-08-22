package com.siteproof.app.verification

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
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
import androidx.core.app.ActivityCompat
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
private val RecoveryAmber = Color(0xFFFFB34D)
private val OverlaySurface = Color(0xFF111318)
private val OverlayLine = Color(0xFF343A43)

private val RequiredVerificationPermissions = listOf(
    Manifest.permission.CAMERA,
    Manifest.permission.RECORD_AUDIO,
    Manifest.permission.ACCESS_FINE_LOCATION,
)

private fun permissionLabel(permission: String): String = when (permission) {
    Manifest.permission.CAMERA -> "Camera"
    Manifest.permission.RECORD_AUDIO -> "Microphone"
    Manifest.permission.ACCESS_FINE_LOCATION -> "Precise location"
    else -> "Required permission"
}

@Composable
fun VerificationScreen(viewModel: VerificationViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val activity = context as? Activity
    var showAbortDialog by remember { mutableStateOf(false) }
    var permissionMessage by remember { mutableStateOf<String?>(null) }
    var permissionRequiresSettings by remember { mutableStateOf(false) }
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
        val missing = RequiredVerificationPermissions.filter { permission ->
            grants[permission] != true &&
                ContextCompat.checkSelfPermission(context, permission) != PackageManager.PERMISSION_GRANTED
        }

        if (missing.isEmpty()) {
            permissionMessage = null
            permissionRequiresSettings = false
            viewModel.permissionsGranted()
        } else {
            val names = missing.map(::permissionLabel).joinToString()
            val blocked = activity != null && missing.any { permission ->
                !ActivityCompat.shouldShowRequestPermissionRationale(activity, permission)
            }
            permissionRequiresSettings = blocked
            permissionMessage = if (blocked) {
                "$names access is disabled for SiteProof. Open App settings, allow the required permissions, then return and check again."
            } else {
                "SiteProof still needs: $names. Allow the requested permissions to start verification."
            }
        }
    }

    fun requestPermissions() {
        permissionMessage = null
        launcher.launch(
            arrayOf(
                Manifest.permission.CAMERA,
                Manifest.permission.RECORD_AUDIO,
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION,
            ),
        )
    }

    fun openAppSettings() {
        val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
            data = Uri.fromParts("package", context.packageName, null)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }

    BackHandler(enabled = state is VerificationUiState.Ready) { viewModel.cancelPrepared(onBack) }
    BackHandler(enabled = live) { showAbortDialog = true }

    if (showAbortDialog) {
        AlertDialog(
            onDismissRequest = { showAbortDialog = false },
            shape = RoundedCornerShape(22.dp),
            title = { Text("Stop verification?") },
            text = { Text("The current live capture will be discarded. You can restart from the inspection.") },
            confirmButton = { TextButton(onClick = { showAbortDialog = false; viewModel.abortByUser() }) { Text("Stop capture") } },
            dismissButton = { TextButton(onClick = { showAbortDialog = false }) { Text("Keep recording") } },
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
                    VerificationUiState.PermissionIntro -> PermissionIntro(
                        onBack = onBack,
                        onContinue = ::requestPermissions,
                        permissionMessage = permissionMessage,
                        requiresSettings = permissionRequiresSettings,
                        onOpenSettings = ::openAppSettings,
                    )
                    VerificationUiState.Preparing -> Loading("Preparing secure capture…")
                    is VerificationUiState.Captured -> CaptureResult(current, viewModel::retryUpload, onBack)
                    is VerificationUiState.Error -> ErrorState(current.message, current.canRetry, viewModel::retryVerification, onBack)
                    else -> Unit
                }
            }
        }
    }
}

private fun cameraPrepared(state: VerificationUiState): VerificationCaptureCoordinator.Prepared? = when (state) {
    is VerificationUiState.Ready -> state.prepared
    is VerificationUiState.StartingCapture -> state.prepared
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

private fun secondsLabel(milliseconds: Long) = "${ceil(milliseconds / 1000.0).toInt()}s"
private fun durationLabel(seconds: Int) = when {
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
        CameraPreview(lifecycleOwner, bindCamera, Modifier.fillMaxSize())
        val requiredSeconds = prepared.session.requiredCaptureDurationSeconds
        CaptureHeader(prepared.inspection.title, state !is VerificationUiState.Ready, state is VerificationUiState.StartingCapture, requiredRemainingMs(state, requiredSeconds))
        when (state) {
            is VerificationUiState.Ready -> ReadyOverlay(prepared, onStart, onBack)
            is VerificationUiState.StartingCapture -> LiveLoadingOverlay("Locking location and starting camera…", onAbort)
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
private fun BoxScope.CaptureHeader(title: String, isRecording: Boolean, isStarting: Boolean, recordingRemaining: Long?) {
    IndustrialOverlay(Modifier.align(Alignment.TopCenter).fillMaxWidth().padding(horizontal = 10.dp, vertical = 10.dp), radius = 18) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 13.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(9.dp)) {
            if (isRecording && !isStarting) Box(Modifier.size(9.dp).background(RecordingRed, CircleShape))
            Column(Modifier.weight(1f)) {
                Text(when { isStarting -> "STARTING CAPTURE"; isRecording -> "LIVE EVIDENCE"; else -> "READY" }, style = MaterialTheme.typography.labelMedium, color = if (isRecording && !isStarting) RecordingRed else MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                Text(title, style = MaterialTheme.typography.titleMedium, color = Color.White, maxLines = 1)
            }
            if (isRecording && !isStarting && recordingRemaining != null) {
                Surface(shape = RoundedCornerShape(999.dp), color = Color(0xFF1D2127), border = BorderStroke(1.dp, OverlayLine)) {
                    Text(if (recordingRemaining > 0L) secondsLabel(recordingRemaining) else "MIN ✓", Modifier.padding(horizontal = 9.dp, vertical = 4.dp), color = Color.White, style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}

@Composable
private fun PermissionIntro(
    onBack: () -> Unit,
    onContinue: () -> Unit,
    permissionMessage: String?,
    requiresSettings: Boolean,
    onOpenSettings: () -> Unit,
) {
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).padding(18.dp), contentAlignment = Alignment.Center) {
        Surface(shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant), shadowElevation = 6.dp) {
            Column(Modifier.padding(21.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Live verification", style = MaterialTheme.typography.headlineMedium)
                Text("Camera, microphone, location and motion data are recorded together so the result can be independently reviewed.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                PermissionLine("Camera", "Records the assigned site while movement instructions appear over the preview.")
                PermissionLine("Microphone", "Records environmental audio with the verification video.")
                PermissionLine("Location", "Checks that capture starts inside the assigned radius.")
                PermissionLine("Motion sensors", "Measures only the requested phone movement.")
                if (!permissionMessage.isNullOrBlank()) {
                    Surface(shape = RoundedCornerShape(14.dp), color = MaterialTheme.colorScheme.errorContainer) {
                        Text(
                            permissionMessage,
                            Modifier.fillMaxWidth().padding(12.dp),
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
                if (requiresSettings) {
                    Button(onClick = onOpenSettings, modifier = Modifier.fillMaxWidth().height(50.dp), shape = RoundedCornerShape(15.dp)) { Text("Open app settings") }
                    TextButton(onClick = onContinue, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Check permissions again") }
                } else {
                    Button(onClick = onContinue, modifier = Modifier.fillMaxWidth().height(50.dp), shape = RoundedCornerShape(15.dp)) {
                        Text(if (permissionMessage == null) "Allow and continue" else "Retry permissions")
                    }
                }
                TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Not now") }
            }
        }
    }
}

@Composable
private fun PermissionLine(title: String, body: String) {
    Surface(shape = RoundedCornerShape(15.dp), color = MaterialTheme.colorScheme.surfaceVariant, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(body, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun BoxScope.ReadyOverlay(prepared: VerificationCaptureCoordinator.Prepared, onStart: () -> Unit, onBack: () -> Unit) {
    val sensorsReady = prepared.capabilities.accelerometer && prepared.capabilities.gyroscope
    IndustrialOverlay(Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(10.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Text("Capture check", style = MaterialTheme.typography.titleLarge, color = Color.White)
            StatusRow("Location", "${prepared.location.accuracyLabel} · ±${prepared.location.location.accuracyMeters.roundToInt()} m")
            StatusRow("Site distance", "${prepared.location.distanceMeters.roundToInt()} m of ${prepared.session.allowedRadiusMeters} m")
            StatusRow("Motion sensors", if (sensorsReady) "Ready" else "Limited")
            StatusRow("Required video", "${durationLabel(prepared.session.requiredCaptureDurationSeconds)} minimum")
            Text("Recording stays active while movement instructions appear on top of the camera.", style = MaterialTheme.typography.bodySmall, color = Color(0xFFB9C0C9))
            Button(onClick = onStart, modifier = Modifier.fillMaxWidth().height(50.dp), shape = RoundedCornerShape(14.dp)) { Text("Start verification") }
            TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Back", color = Color(0xFFCDD2D8)) }
        }
    }
}

@Composable
private fun BoxScope.ChallengeActiveOverlay(state: VerificationUiState.ChallengeActive, onAbort: () -> Unit) {
    IndustrialOverlay(Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(10.dp)) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                Text("MOVEMENT", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                Text("${state.challenge.sequenceNumber}/${state.challenge.totalChallenges}", style = MaterialTheme.typography.labelMedium, color = Color(0xFFB9C0C9))
            }
            ChallengeMovementGuide(state.challenge, state.guidance)
            Text(state.feedback, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 2.dp))
            Text("${secondsLabel(state.remainingMs)} remaining · keep the site in frame", style = MaterialTheme.typography.bodySmall, color = Color(0xFFADB4BD), modifier = Modifier.padding(top = 3.dp))
            TextButton(onClick = onAbort) { Text("Stop capture", color = Color(0xFFB9C0C9)) }
        }
    }
}

@Composable
private fun BoxScope.LiveLoadingOverlay(message: String, onAbort: () -> Unit) {
    IndustrialOverlay(Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(10.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator(Modifier.size(30.dp), strokeWidth = 3.dp)
            Text(message, color = Color.White, textAlign = TextAlign.Center, modifier = Modifier.padding(9.dp))
            Text("Recording continues.", color = Color(0xFFADB4BD), style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = onAbort) { Text("Stop capture", color = Color(0xFFB9C0C9)) }
        }
    }
}

@Composable
private fun BoxScope.NetworkWaitOverlay(state: VerificationUiState.ChallengeNetworkWait, retry: () -> Unit, onAbort: () -> Unit) {
    IndustrialOverlay(Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(10.dp), borderColor = RecoveryAmber.copy(alpha = .62f)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Connection interrupted", style = MaterialTheme.typography.titleLarge, color = RecoveryAmber)
            Text(state.message, color = Color.White, textAlign = TextAlign.Center, modifier = Modifier.padding(vertical = 7.dp))
            Text("Evidence recording is still active. Reconnect and continue without restarting.", style = MaterialTheme.typography.bodySmall, color = Color(0xFFADB4BD), textAlign = TextAlign.Center)
            Button(onClick = retry, modifier = Modifier.fillMaxWidth().padding(top = 12.dp), shape = RoundedCornerShape(14.dp)) { Text("Reconnect") }
            TextButton(onClick = onAbort) { Text("Stop capture", color = Color(0xFFB9C0C9)) }
        }
    }
}

@Composable
private fun BoxScope.ChallengeResultOverlay(result: ChallengeValidationResult, retryChallenge: () -> Unit, onAbort: () -> Unit) {
    val passed = result.result == "PASS"
    val title = when { passed -> "Movement verified"; result.result == "FAIL" -> "Movement not verified"; else -> "Movement inconclusive" }
    val detail = when { passed -> "The next movement will appear automatically while recording continues."; result.retryAllowed -> "Recording is safe. Retry this movement with a fresh challenge."; else -> "This step cannot be retried. Stop and restart verification from the inspection." }
    IndustrialOverlay(Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(10.dp), borderColor = if (passed) MaterialTheme.colorScheme.primary.copy(alpha = .6f) else MaterialTheme.colorScheme.error.copy(alpha = .65f)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(title, style = MaterialTheme.typography.titleLarge, color = if (passed) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
            Text(detail, color = Color(0xFFC4CAD1), textAlign = TextAlign.Center, modifier = Modifier.padding(7.dp))
            if (!passed && result.retryAllowed) Button(onClick = retryChallenge, modifier = Modifier.fillMaxWidth().padding(top = 5.dp), shape = RoundedCornerShape(14.dp)) { Text("Retry challenge") }
            TextButton(onClick = onAbort) { Text("Stop capture", color = Color(0xFFB9C0C9)) }
        }
    }
}

@Composable
private fun BoxScope.CaptureFinishingOverlay(state: VerificationUiState.CaptureFinishing, onAbort: () -> Unit) {
    val requiredMs = state.prepared.session.requiredCaptureDurationSeconds * 1_000f
    val progress = (state.elapsedMs / requiredMs).coerceIn(0f, 1f)
    IndustrialOverlay(Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(10.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Text("Movement checks complete", style = MaterialTheme.typography.titleLarge, color = Color.White, textAlign = TextAlign.Center)
            Text(if (state.remainingMs > 0L) "Keep the site steady · ${secondsLabel(state.remainingMs)} minimum recording remaining" else "Minimum recording reached. Sealing evidence…", textAlign = TextAlign.Center, color = Color(0xFFB9C0C9))
            LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primary, trackColor = Color(0xFF2D323A))
            TextButton(onClick = onAbort) { Text("Stop capture", color = Color(0xFFB9C0C9)) }
        }
    }
}

private fun isLiveState(state: VerificationUiState) = when (state) {
    is VerificationUiState.StartingCapture,
    is VerificationUiState.ChallengeLoading,
    is VerificationUiState.ChallengeActive,
    is VerificationUiState.ChallengeChecking,
    is VerificationUiState.ChallengeNetworkWait,
    is VerificationUiState.ChallengeResultState,
    is VerificationUiState.CaptureFinishing -> true
    else -> false
}

@Composable
private fun CameraPreview(lifecycleOwner: LifecycleOwner, bindCamera: (PreviewView, LifecycleOwner) -> Unit, modifier: Modifier) {
    AndroidView(
        modifier = modifier,
        factory = { context -> PreviewView(context).apply { implementationMode = PreviewView.ImplementationMode.COMPATIBLE; scaleType = PreviewView.ScaleType.FILL_CENTER }.also { bindCamera(it, lifecycleOwner) } },
    )
}

@Composable
private fun CaptureResult(state: VerificationUiState.Captured, retry: (String) -> Unit, onBack: () -> Unit) {
    Box(Modifier.fillMaxSize().padding(18.dp), contentAlignment = Alignment.Center) {
        Surface(shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant), shadowElevation = 6.dp) {
            Column(Modifier.fillMaxWidth().padding(21.dp), verticalArrangement = Arrangement.spacedBy(11.dp)) {
                Text("Evidence saved", style = MaterialTheme.typography.headlineMedium)
                Text(state.message, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (state.uploadStatus == "UPLOADING" && state.progressPercent != null) {
                    LinearProgressIndicator(progress = { (state.progressPercent / 100f).coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
                    Text("${state.progressPercent}%${state.networkLabel?.let { " · $it" }.orEmpty()}", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                }
                if (state.uploadStatus == "FAILED") {
                    Surface(shape = RoundedCornerShape(14.dp), color = MaterialTheme.colorScheme.errorContainer) { Text("Upload failed, but evidence remains safely queued on this device.", Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onErrorContainer) }
                    Button(onClick = { retry(state.sessionId) }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp)) { Text("Retry upload") }
                }
                if (state.uploadStatus == "UPLOADED") Button(onClick = onBack, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp)) { Text("Done") }
            }
        }
    }
}

@Composable
private fun ErrorState(message: String, canRetry: Boolean, retry: () -> Unit, onBack: () -> Unit) {
    val friendly = friendlyError(message)
    Box(Modifier.fillMaxSize().padding(18.dp), contentAlignment = Alignment.Center) {
        Surface(shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = .28f)), shadowElevation = 6.dp) {
            Column(Modifier.fillMaxWidth().padding(21.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Surface(Modifier.size(50.dp), shape = CircleShape, color = MaterialTheme.colorScheme.errorContainer) { Box(contentAlignment = Alignment.Center) { Text("!", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.onErrorContainer, fontWeight = FontWeight.Bold) } }
                Text(friendly.first, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
                Text(friendly.second, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
                Surface(shape = RoundedCornerShape(12.dp), color = MaterialTheme.colorScheme.surfaceVariant) { Text(message, Modifier.padding(10.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center) }
                if (canRetry) Button(onClick = retry, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp)) { Text("Try again") }
                TextButton(onClick = onBack) { Text("Back to inspection") }
            }
        }
    }
}

private fun friendlyError(message: String): Pair<String, String> {
    val normalized = message.lowercase()
    return when {
        "permission" in normalized || "camera" in normalized && "denied" in normalized || "microphone" in normalized -> "Capture permissions are needed" to "Allow camera, microphone and precise location access, then retry."
        "location" in normalized || "gps" in normalized -> "Location could not be confirmed" to "Enable location services, move to an open area and try again."
        "sensor" in normalized || "gyro" in normalized || "accelerometer" in normalized -> "Motion sensing is unavailable" to "Keep the phone steady and retry. This device may not support the required challenge if the error continues."
        "network" in normalized || "connection" in normalized || "timeout" in normalized -> "Connection unavailable" to "Check the connection. Evidence is retained whenever the workflow can safely retry."
        else -> "Verification could not continue" to "Nothing was submitted incorrectly. Retry or return to the inspection."
    }
}

@Composable
private fun Loading(message: String) {
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        CircularProgressIndicator()
        Text(message, Modifier.padding(18.dp), textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun StatusRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = Color(0xFF9EA6B0), style = MaterialTheme.typography.bodySmall)
        Text(value, color = Color.White, fontWeight = FontWeight.Medium, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun IndustrialOverlay(
    modifier: Modifier,
    radius: Int = 22,
    borderColor: Color = OverlayLine,
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(radius.dp),
        color = OverlaySurface.copy(alpha = .94f),
        border = BorderStroke(1.dp, borderColor),
        shadowElevation = 7.dp,
        content = content,
    )
}
