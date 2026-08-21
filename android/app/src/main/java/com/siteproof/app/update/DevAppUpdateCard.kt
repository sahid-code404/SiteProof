package com.siteproof.app.update

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.siteproof.app.BuildConfig
import java.io.File
import kotlinx.coroutines.launch

@Composable
fun DevAppUpdateCard(manager: DevAppUpdateManager) {
    if (!BuildConfig.DEBUG) return

    val scope = rememberCoroutineScope()
    var checking by remember { mutableStateOf(false) }
    var downloading by remember { mutableStateOf(false) }
    var update by remember { mutableStateOf<AppUpdateInfo?>(null) }
    var downloadedApk by remember { mutableStateOf<File?>(null) }
    var status by remember { mutableStateOf("Checking for updates…") }

    fun checkNow() {
        if (checking || downloading) return
        checking = true
        status = "Checking for updates…"
        scope.launch {
            runCatching { manager.checkForUpdate() }
                .onSuccess { available ->
                    update = available
                    downloadedApk = null
                    status = if (available == null) {
                        "SiteProof is up to date."
                    } else {
                        "Update available: version ${available.versionName}."
                    }
                }
                .onFailure { error ->
                    status = error.message ?: "Unable to check for updates."
                }
            checking = false
        }
    }

    LaunchedEffect(Unit) { checkNow() }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        "App update",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "Current version ${BuildConfig.VERSION_NAME}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                OutlinedButton(onClick = ::checkNow, enabled = !checking && !downloading) {
                    Text(if (checking) "Checking…" else "Check now")
                }
            }

            Text(
                status,
                style = MaterialTheme.typography.bodyMedium,
                color = if (status.contains("failed", ignoreCase = true) ||
                    status.contains("unable", ignoreCase = true)
                ) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )

            update?.notes?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
            }

            if (downloading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text(
                    "Downloading and verifying the update…",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            val available = update
            if (available != null) {
                Button(
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !checking && !downloading,
                    onClick = {
                        val existing = downloadedApk
                        if (existing != null && existing.isFile) {
                            val result = manager.launchInstaller(existing)
                            status = if (result == InstallLaunchResult.PERMISSION_REQUIRED) {
                                "Allow SiteProof to install this update, return here, then tap Install update."
                            } else {
                                "Android installer opened. Confirm the update to finish."
                            }
                            return@Button
                        }

                        downloading = true
                        status = "Preparing version ${available.versionName}…"
                        scope.launch {
                            runCatching { manager.download(available) }
                                .onSuccess { apk ->
                                    downloadedApk = apk
                                    val result = manager.launchInstaller(apk)
                                    status = if (result == InstallLaunchResult.PERMISSION_REQUIRED) {
                                        "Allow SiteProof to install this update, return here, then tap Install update."
                                    } else {
                                        "Android installer opened. Confirm the update to finish."
                                    }
                                }
                                .onFailure { error ->
                                    status = error.message ?: "Update download failed."
                                }
                            downloading = false
                        }
                    },
                ) {
                    Text(
                        when {
                            downloading -> "Downloading…"
                            downloadedApk != null -> "Install update"
                            else -> "Update now"
                        }
                    )
                }

                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !checking && !downloading,
                    onClick = {
                        update = null
                        downloadedApk = null
                        status = "Update postponed. You can check again anytime."
                    },
                ) {
                    Text("Later")
                }
            }
        }
    }
}
