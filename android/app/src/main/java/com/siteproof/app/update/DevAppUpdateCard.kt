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
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.unit.dp
import com.siteproof.app.BuildConfig
import java.io.File
import kotlinx.coroutines.launch

@Composable
fun DevAppUpdateCard(manager: DevAppUpdateManager) {
    if (!BuildConfig.DEBUG) return

    val scope = rememberCoroutineScope()
    var downloading by remember { mutableStateOf(false) }
    var update by remember { mutableStateOf<AppUpdateInfo?>(null) }
    var downloadedApk by remember { mutableStateOf<File?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var messageIsError by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        runCatching { manager.checkForUpdate() }
            .onSuccess { update = it }
        // Update checks stay silent when the device is offline or the channel is unavailable.
        // They are not part of the inspector's primary workflow.
    }

    val available = update ?: return

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .padding(16.dp)
                .semantics { liveRegion = LiveRegionMode.Polite },
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("Update available", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Version ${available.versionName}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    "v${BuildConfig.VERSION_NAME}",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            available.notes?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
            }

            if (downloading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text(
                    "Downloading update…",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            message?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = if (messageIsError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Button(
                modifier = Modifier.fillMaxWidth(),
                enabled = !downloading,
                onClick = {
                    val existing = downloadedApk
                    if (existing != null && existing.isFile) {
                        val result = manager.launchInstaller(existing)
                        messageIsError = false
                        message = if (result == InstallLaunchResult.PERMISSION_REQUIRED) {
                            "Allow installs from SiteProof, then return and tap Install update."
                        } else {
                            "Confirm the update in Android."
                        }
                        return@Button
                    }

                    downloading = true
                    message = null
                    messageIsError = false
                    scope.launch {
                        runCatching { manager.download(available) }
                            .onSuccess { apk ->
                                downloadedApk = apk
                                val result = manager.launchInstaller(apk)
                                message = if (result == InstallLaunchResult.PERMISSION_REQUIRED) {
                                    "Allow installs from SiteProof, then return and tap Install update."
                                } else {
                                    "Confirm the update in Android."
                                }
                            }
                            .onFailure { error ->
                                messageIsError = true
                                message = error.message ?: "Could not download the update."
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
                    },
                )
            }

            TextButton(
                modifier = Modifier.align(Alignment.End),
                enabled = !downloading,
                onClick = {
                    update = null
                    downloadedApk = null
                    message = null
                },
            ) {
                Text("Later")
            }
        }
    }
}
