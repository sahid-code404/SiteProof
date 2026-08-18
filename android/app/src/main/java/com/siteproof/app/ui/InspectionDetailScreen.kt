package com.siteproof.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private fun detailDeadline(value: String): String = runCatching {
    OffsetDateTime.parse(value).format(DateTimeFormatter.ofPattern("dd MMM yyyy, h:mm a", Locale.getDefault()))
}.getOrDefault(value)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InspectionDetailScreen(
    state: InspectionDetailState,
    onBack: () -> Unit,
    onRetry: () -> Unit,
    onAcknowledge: () -> Unit,
    onReady: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Inspection details") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, contentDescription = "Back") } },
            )
        },
    ) { padding ->
        when {
            state.loading -> Column(
                modifier = Modifier.padding(padding).fillMaxSize(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) { CircularProgressIndicator() }
            state.item == null -> Column(
                modifier = Modifier.padding(padding).fillMaxSize().padding(28.dp),
                verticalArrangement = Arrangement.Center,
            ) {
                Text("Unable to load inspection.", style = MaterialTheme.typography.headlineSmall)
                Text(state.error ?: "Unknown error", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 12.dp))
                Button(onClick = onRetry) { Text("Retry") }
            }
            else -> {
                val item = state.item
                Column(
                    modifier = Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
                ) {
                    if (state.offline) {
                        Text("Offline — showing last synced data", color = MaterialTheme.colorScheme.tertiary, style = MaterialTheme.typography.labelLarge)
                        Spacer(Modifier.height(12.dp))
                    }
                    Text(item.title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.SemiBold)
                    Row(modifier = Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(item.status, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                        Text(item.priority, color = MaterialTheme.colorScheme.tertiary, fontWeight = FontWeight.Bold)
                    }
                    HorizontalDivider(Modifier.padding(vertical = 20.dp))
                    DetailField("Location", item.locationName ?: item.locationAddress ?: "${item.expectedLatitude}, ${item.expectedLongitude}")
                    DetailField("Distance", "Distance unavailable")
                    DetailField("Allowed verification radius", "${item.allowedRadiusMeters} m")
                    DetailField("Deadline", detailDeadline(item.deadline))
                    DetailField("Inspection type", item.inspectionType.replace('_', ' '))
                    DetailField("Instructions", item.instructions ?: "No additional instructions.")
                    if (state.error != null) {
                        Text(state.error, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 12.dp))
                    }
                    Spacer(Modifier.height(20.dp))
                    when (item.status) {
                        "ASSIGNED" -> Button(
                            onClick = onAcknowledge,
                            enabled = !state.actionInProgress && !state.offline,
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(if (state.actionInProgress) "UPDATING…" else "ACKNOWLEDGE") }
                        "ACKNOWLEDGED" -> Button(
                            onClick = onReady,
                            enabled = !state.actionInProgress && !state.offline,
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(if (state.actionInProgress) "UPDATING…" else "MARK READY") }
                        "READY" -> Text(
                            "Verification ready",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                    Spacer(Modifier.height(24.dp))
                    Text(
                        "Live verification is intentionally not available in Phase 2.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun DetailField(label: String, value: String) {
    Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Text(value, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.padding(top = 3.dp, bottom = 16.dp))
}
