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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
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
        val camera = grants[Manifest.permission.CAMERA] == true ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        val fine = grants[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (camera && fine) viewModel.permissionsGranted()
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
            title = { Text("Cancel live verification?") },
            text = {
                Text("The continuous capture and active challenge will be discarded. A new session will be required.")
            },
            confirmButton = {
                TextButton(onClick = { showAbortDialog = false; viewModel.abortByUser() }) { Text("Abort") }
            },
            dismissButton = {
                TextButton(onClick = { showAbortDialog = false }) { Text("Continue") }
            },
        )
    }

    Scaffold { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            when (val current = state) {
                VerificationUiState.PermissionIntro -> PermissionIntro(onBack, ::requestPermissions)
                VerificationUiState.Preparing -> Loading("Acquiring fresh location and preparing verification…")
                is VerificationUiState.Ready -> ReadyCapture(
                    current.prepared,
                    lifecycleOwner,
                    viewModel::bindCamera,
                    viewModel::startCapture,
                    { viewModel.cancelPrepared(onBack) },
                )
                is VerificationUiState.ChallengeLoading -> LiveLoading(
                    current.prepared,
                    lifecycleOwner,
                    viewModel::bindCamera,
                    "Requesting an unpredictable server challenge…",
                    { showAbortDialog = true },
                )
                is VerificationUiState.ChallengeActive -> ChallengeActiveScreen(
                    current,
                    lifecycleOwner,
                    viewModel::bindCamera,
                    { showAbortDialog = true },
                )
                is VerificationUiState.ChallengeChecking -> LiveLoading(
                    current.prepared,
                    lifecycleOwner,
                    viewModel::bindCamera,
                    "Checking movement with the server…",
                    { showAbortDialog = true },
                )
                is VerificationUiState.ChallengeNetworkWait -> NetworkWaitScreen(
                    current,
                    lifecycleOwner,
                    viewModel::bindCamera,
                    viewModel::retryChallengeConnection,
                    { showAbortDialog = true },
                )
                is VerificationUiState.ChallengeResultState -> ChallengeResultScreen(
                    current.prepared,
                    current.result,
                    lifecycleOwner,
                    viewModel::bindCamera,
                    viewModel::retryChallenge,
                    { showAbortDialog = true },
                )
                is VerificationUiState.Captured -> CaptureResult(current, viewModel::retryUpload, onBack)
                is VerificationUiState.Error -> ErrorState(
                    current.message,
                    current.canRetry,
                    viewModel::retryVerification,
                    onBack,
                )
            }
        }
    }
}

@Composable
private fun PermissionIntro(onBack: () -> Unit, onContinue: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.Center) {
        Text("SITE VERIFICATION", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        Text("Live proof-of-presence", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(top = 8.dp, bottom = 24.dp))
        Text("Camera", style = MaterialTheme.typography.titleMedium)
        Text("Records one continuous live view of the inspection site. Gallery uploads are not supported.")
        Spacer(Modifier.height(16.dp))
        Text("Location", style = MaterialTheme.typography.titleMedium)
        Text("Checks that capture starts near the assigned inspection site.")
        Spacer(Modifier.height(16.dp))
        Text("Motion challenges", style = MaterialTheme.typography.titleMedium)
        Text("Follow the animated phone and arrow. You do not need to estimate an exact angle; move until the guide turns green.")
        Spacer(Modifier.height(28.dp))
        Button(onClick = onContinue, modifier = Modifier.fillMaxWidth()) { Text("CONTINUE") }
        TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Back") }
    }
}

@Composable
private fun ReadyCapture(
    prepared: VerificationCaptureCoordinator.Prepared,
    lifecycleOwner: LifecycleOwner,
    bindCamera: (PreviewView, LifecycleOwner) -> Unit,
    onStart: () -> Unit,
    onBack: () -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Text("SITE VERIFICATION", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        Text(prepared.inspection.title, style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        CameraPreview(lifecycleOwner, bindCamera, Modifier.fillMaxWidth().weight(1f))
        Spacer(Modifier.height(12.dp))
        StatusRow("GPS", "${prepared.location.accuracyLabel} · ±${prepared.location.location.accuracyMeters.roundToInt()} m")
        StatusRow("Distance", "${prepared.location.distanceMeters.roundToInt()} m / ${prepared.inspection.allowedRadiusMeters} m allowed")
        StatusRow("Accelerometer", if (prepared.capabilities.accelerometer) "Ready" else "Unavailable")
        StatusRow("Gyroscope", if (prepared.capabilities.gyroscope) "Ready" else "Unavailable")
        StatusRow("Rotation vector", if (prepared.capabilities.rotationVector) "Ready" else "Unavailable · reduced confidence")
        Text("Keep the site visible while following three short animated movement challenges.", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 12.dp))
        Button(onClick = onStart, modifier = Modifier.fillMaxWidth()) { Text("START LIVE VERIFICATION") }
        TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Back") }
    }
}

@Composable
private fun ChallengeActiveScreen(
    state: VerificationUiState.ChallengeActive,
    lifecycleOwner: LifecycleOwner,
    bindCamera: (PreviewView, LifecycleOwner) -> Unit,
    onAbort: () -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            "CHALLENGE ${state.challenge.sequenceNumber} OF ${state.challenge.totalChallenges}",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(
            "Keep the inspection site visible while moving the phone.",
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
        )
        CameraPreview(lifecycleOwner, bindCamera, Modifier.fillMaxWidth().height(205.dp))
        Spacer(Modifier.height(10.dp))
        ChallengeMovementGuide(state.challenge, state.guidance)
        Text(
            state.feedback,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 5.dp),
        )
        Text(
            "${ceil(state.remainingMs / 1000.0).toInt()} sec remaining",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(top = 5.dp),
        )
        TextButton(onClick = onAbort) { Text("Abort verification") }
    }
}

@Composable
private fun LiveLoading(
    prepared: VerificationCaptureCoordinator.Prepared,
    lifecycleOwner: LifecycleOwner,
    bindCamera: (PreviewView, LifecycleOwner) -> Unit,
    message: String,
    onAbort: () -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text("LIVE VERIFICATION", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        Text(prepared.inspection.title, style = MaterialTheme.typography.titleMedium)
        CameraPreview(lifecycleOwner, bindCamera, Modifier.fillMaxWidth().weight(1f))
        CircularProgressIndicator(modifier = Modifier.padding(top = 16.dp))
        Text(message, textAlign = TextAlign.Center, modifier = Modifier.padding(12.dp))
        TextButton(onClick = onAbort) { Text("Abort verification") }
    }
}

@Composable
private fun NetworkWaitScreen(
    state: VerificationUiState.ChallengeNetworkWait,
    lifecycleOwner: LifecycleOwner,
    bindCamera: (PreviewView, LifecycleOwner) -> Unit,
    retry: () -> Unit,
    onAbort: () -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text("CONNECTION LOST", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.error)
        CameraPreview(lifecycleOwner, bindCamera, Modifier.fillMaxWidth().weight(1f))
        Text(state.message, textAlign = TextAlign.Center, modifier = Modifier.padding(vertical = 16.dp))
        Text("No future challenge is available until the server reconnects.", style = MaterialTheme.typography.bodySmall)
        Button(onClick = retry, modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) { Text("RETRY CONNECTION") }
        TextButton(onClick = onAbort) { Text("Abort verification") }
    }
}

@Composable
private fun ChallengeResultScreen(
    prepared: VerificationCaptureCoordinator.Prepared,
    result: ChallengeValidationResult,
    lifecycleOwner: LifecycleOwner,
    bindCamera: (PreviewView, LifecycleOwner) -> Unit,
    retryChallenge: () -> Unit,
    onAbort: () -> Unit,
) {
    val title = when (result.result) {
        "PASS" -> "Challenge completed ✓"
        "FAIL" -> "Movement could not be verified"
        else -> "Challenge was inconclusive"
    }
    val detail = when (result.result) {
        "PASS" -> "Movement verified. Preparing the next challenge…"
        else -> if (result.retryAllowed) {
            "You can retry with a fresh server challenge. The completed sensor window and nonce will never be reused."
        } else {
            "No challenge retry remains. Continuing with the recorded result."
        }
    }
    Column(Modifier.fillMaxSize().padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text("LIVE VERIFICATION", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        Text(prepared.inspection.title, style = MaterialTheme.typography.titleMedium)
        CameraPreview(lifecycleOwner, bindCamera, Modifier.fillMaxWidth().weight(1f))
        Text(title, style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 16.dp))
        Text(detail, textAlign = TextAlign.Center, modifier = Modifier.padding(8.dp))
        if (result.result != "PASS" && result.retryAllowed) {
            Button(onClick = retryChallenge, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Text("RETRY CHALLENGE")
            }
        }
        TextButton(onClick = onAbort) { Text("Abort verification") }
    }
}

private fun isLiveState(state: VerificationUiState): Boolean = when (state) {
    is VerificationUiState.ChallengeLoading,
    is VerificationUiState.ChallengeActive,
    is VerificationUiState.ChallengeChecking,
    is VerificationUiState.ChallengeNetworkWait,
    is VerificationUiState.ChallengeResultState,
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
        factory = { context -> PreviewView(context).also { bindCamera(it, lifecycleOwner) } },
    )
}

@Composable
private fun CaptureResult(state: VerificationUiState.Captured, retry: (String) -> Unit, onBack: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.Center) {
        Text("Evidence Captured", style = MaterialTheme.typography.headlineMedium)
        Text(state.message, modifier = Modifier.padding(vertical = 16.dp))
        Text("Final SiteProof authenticity has not been calculated yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (state.uploadStatus == "FAILED") {
            Button(onClick = { retry(state.sessionId) }, modifier = Modifier.fillMaxWidth().padding(top = 24.dp)) {
                Text("RETRY UPLOAD")
            }
        }
        if (state.uploadStatus == "UPLOADED") {
            Button(onClick = onBack, modifier = Modifier.fillMaxWidth().padding(top = 24.dp)) { Text("DONE") }
        }
    }
}

@Composable
private fun ErrorState(message: String, canRetry: Boolean, retry: () -> Unit, onBack: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.Center) {
        Text("Verification unavailable", style = MaterialTheme.typography.headlineSmall)
        Text(message, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 16.dp))
        if (canRetry) Button(onClick = retry, modifier = Modifier.fillMaxWidth()) { Text("RETRY VERIFICATION") }
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
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value)
    }
}
