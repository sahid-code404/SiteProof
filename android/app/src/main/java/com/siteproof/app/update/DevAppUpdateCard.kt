package com.siteproof.app.update

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
    var status by remember { mutableStateOf("Checking for a newer field-test build…") }

    fun checkNow() {
        if (checking || downloading) return
        checking = true
        status = "Checking for update…"
        scope.launch {
            runCatching { manager.checkForUpdate() }
                .onSuccess { available ->
                    update = available
                    downloadedApk = null
                    status = if (available == null) {
                        "This field-test build is up to date."
                    } else {
                        "Version ${available.versionName} is ready."
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
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        "Field-test app update",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "Installed ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                OutlinedButton(onClick = ::checkNow, enabled = !checking && !downloading) {
                    Text(if (checking) "Checking…" else "Check")
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
            )

            update?.notes?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
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
                                "Allow installs from SiteProof Dev, return here, then tap Install update."
                            } else {
                                "Android installer opened. Confirm the update to finish."
                            }
                            return@Button
                        }

                        downloading = true
                        status = "Downloading and verifying ${available.versionName}…"
                        scope.launch {
                            runCatching { manager.download(available) }
                                .onSuccess { apk ->
                                    downloadedApk = apk
                                    val result = manager.launchInstaller(apk)
                                    status = if (result == InstallLaunchResult.PERMISSION_REQUIRED) {
                                        "Allow installs from SiteProof Dev, return here, then tap Install update."
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
                            else -> "Download & install"
                        }
                    )
                }
            }
        }
    }
}
