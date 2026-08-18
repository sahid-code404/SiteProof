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
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
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

    DisposableEffect(activity) {
        activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        onDispose { activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE) }
    }
    DisposableEffect(lifecycleOwner, state) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP && state is VerificationUiState.Capturing) {
                viewModel.abortForInterruption()
            }
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
        arrayOf(Manifest.permission.CAMERA, Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION),
    )

    BackHandler(enabled = state is VerificationUiState.Capturing) { showAbortDialog = true }
    if (showAbortDialog) {
        AlertDialog(
            onDismissRequest = { showAbortDialog = false },
            title = { Text("Cancel verification?") },
            text = { Text("The current live capture will be discarded and this session will be marked aborted.") },
            confirmButton = { TextButton(onClick = { showAbortDialog = false; viewModel.abortByUser() }) { Text("Abort") } },
            dismissButton = { TextButton(onClick = { showAbortDialog = false }) { Text("Continue capture") } },
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
                    onBack,
                )
                is VerificationUiState.Capturing -> LiveCapture(
                    current,
                    lifecycleOwner,
                    viewModel::bindCamera,
                    viewModel::stopCapture,
                    { showAbortDialog = true },
                )
                is VerificationUiState.Captured -> CaptureResult(current, viewModel::retryUpload, onBack)
                is VerificationUiState.Error -> ErrorState(current.message, current.canRetry, viewModel::prepare, onBack)
            }
        }
    }
}

@Composable
private fun PermissionIntro(onBack: () -> Unit, onContinue: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.Center) {
        Text("SITE VERIFICATION", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        Text("Live evidence capture", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(top = 8.dp, bottom = 24.dp))
        Text("Camera", style = MaterialTheme.typography.titleMedium)
        Text("Records live site evidence. Gallery uploads are not supported.")
        Spacer(Modifier.height(16.dp))
        Text("Location", style = MaterialTheme.typography.titleMedium)
        Text("Checks that capture occurs near the assigned inspection site.")
        Spacer(Modifier.height(16.dp))
        Text("Motion sensors", style = MaterialTheme.typography.titleMedium)
        Text("Accelerometer, gyroscope and rotation-vector data are collected only during verification.")
        Spacer(Modifier.height(28.dp))
        Button(onClick = onContinue, modifier = Modifier.fillMaxWidth()) { Text("CONTINUE") }
        TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Back") }
    }
}

@Composable
private fun ReadyCapture(
    prepared: VerificationCaptureCoordinator.Prepared,
    lifecycleOwner: androidx.lifecycle.LifecycleOwner,
    bindCamera: (PreviewView, androidx.lifecycle.LifecycleOwner) -> Unit,
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
        StatusRow("Gyroscope", if (prepared.capabilities.gyroscope) "Ready" else "Unavailable · reduced strength")
        StatusRow("Rotation vector", if (prepared.capabilities.rotationVector) "Ready" else "Unavailable · reduced strength")
        Text("Estimated capture: 15–30 seconds", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 12.dp))
        Button(onClick = onStart, modifier = Modifier.fillMaxWidth()) { Text("START LIVE CAPTURE") }
        TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Back") }
    }
}

@Composable
private fun LiveCapture(
    state: VerificationUiState.Capturing,
    lifecycleOwner: androidx.lifecycle.LifecycleOwner,
    bindCamera: (PreviewView, androidx.lifecycle.LifecycleOwner) -> Unit,
    onStop: () -> Unit,
    onAbort: () -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Text("LIVE VERIFICATION", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        CameraPreview(lifecycleOwner, bindCamera, Modifier.fillMaxWidth().weight(1f))
        Text("GPS ✓    Sensors ✓    Session ACTIVE", modifier = Modifier.padding(top = 12.dp))
        Text("%02d:%02d".format((state.elapsedMs / 1000) / 60, (state.elapsedMs / 1000) % 60), style = MaterialTheme.typography.headlineMedium)
        Button(
            onClick = onStop,
            enabled = state.elapsedMs >= 8_000L,
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        ) { Text(if (state.elapsedMs < 8_000L) "CAPTURE AT LEAST 8 SECONDS" else "STOP CAPTURE") }
        TextButton(onClick = onAbort, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Abort") }
    }
}

@Composable
private fun CameraPreview(
    lifecycleOwner: androidx.lifecycle.LifecycleOwner,
    bindCamera: (PreviewView, androidx.lifecycle.LifecycleOwner) -> Unit,
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
        Text("Verification has not been analyzed yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (state.uploadStatus == "FAILED") {
            Button(onClick = { retry(state.sessionId) }, modifier = Modifier.fillMaxWidth().padding(top = 24.dp)) { Text("RETRY NOW") }
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
        if (canRetry) Button(onClick = retry, modifier = Modifier.fillMaxWidth()) { Text("TRY AGAIN") }
        TextButton(onClick = onBack, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Back") }
    }
}

@Composable
private fun Loading(message: String) {
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        CircularProgressIndicator()
        Text(message, modifier = Modifier.padding(20.dp))
    }
}

@Composable
private fun StatusRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value)
    }
}
