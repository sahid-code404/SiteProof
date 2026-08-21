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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
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
    onStartVerification: () -> Unit,
) {
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = { Text("Inspection") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        when {
            state.loading -> LoadingDetail(Modifier.padding(padding))
            state.item == null -> MissingDetail(
                modifier = Modifier.padding(padding),
                message = state.error ?: "Inspection not found.",
                onRetry = onRetry,
            )
            else -> {
                val item = state.item
                Column(
                    modifier = Modifier
                        .padding(padding)
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    if (state.offline) {
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            color = MaterialTheme.colorScheme.tertiary.copy(alpha = 0.10f),
                        ) {
                            Column(Modifier.padding(14.dp)) {
                                Text("Offline", color = MaterialTheme.colorScheme.tertiary, fontWeight = FontWeight.SemiBold)
                                Text(
                                    "Showing the last synced copy.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }

                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(item.title, style = MaterialTheme.typography.headlineMedium)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            DetailChip(item.status)
                            DetailChip(item.priority)
                        }
                    }

                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                            DetailField(
                                "Location",
                                item.locationName ?: item.locationAddress ?: "${item.expectedLatitude}, ${item.expectedLongitude}",
                            )
                            DetailField("Capture area", "Within ${item.allowedRadiusMeters} m")
                            DetailField("Deadline", detailDeadline(item.deadline))
                            DetailField("Type", item.inspectionType.replace('_', ' '))
                        }
                    }

                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Instructions", style = MaterialTheme.typography.titleMedium)
                            Text(
                                item.instructions ?: "No additional instructions.",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }

                    state.error?.let {
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                    }

                    InspectionAction(
                        status = item.status,
                        actionInProgress = state.actionInProgress,
                        offline = state.offline,
                        onAcknowledge = onAcknowledge,
                        onReady = onReady,
                        onStartVerification = onStartVerification,
                    )

                    if (item.status == "SESSION_STARTED" || item.status == "EVIDENCE_UPLOADING") {
                        StatusMessage("Live verification is in progress.")
                    } else if (item.status == "PROCESSING") {
                        StatusMessage("Evidence uploaded. Verification is processing.")
                    }

                    Spacer(Modifier.height(8.dp))
                }
            }
        }
    }
}

@Composable
private fun InspectionAction(
    status: String,
    actionInProgress: Boolean,
    offline: Boolean,
    onAcknowledge: () -> Unit,
    onReady: () -> Unit,
    onStartVerification: () -> Unit,
) {
    when (status) {
        "ASSIGNED" -> Button(
            onClick = onAcknowledge,
            enabled = !actionInProgress && !offline,
            modifier = Modifier.fillMaxWidth().height(50.dp),
        ) { Text(if (actionInProgress) "Updating…" else "Acknowledge") }

        "ACKNOWLEDGED" -> Button(
            onClick = onReady,
            enabled = !actionInProgress && !offline,
            modifier = Modifier.fillMaxWidth().height(50.dp),
        ) { Text(if (actionInProgress) "Updating…" else "Mark ready") }

        "READY" -> Button(
            onClick = onStartVerification,
            enabled = !offline,
            modifier = Modifier.fillMaxWidth().height(50.dp),
        ) { Text("Start verification") }
    }
}

@Composable
private fun DetailField(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun DetailChip(value: String) {
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = MaterialTheme.colorScheme.primaryContainer,
    ) {
        Text(
            value.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() },
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onPrimaryContainer,
        )
    }
}

@Composable
private fun StatusMessage(message: String) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.primaryContainer,
    ) {
        Text(
            message,
            modifier = Modifier.padding(14.dp),
            color = MaterialTheme.colorScheme.onPrimaryContainer,
        )
    }
}

@Composable
private fun LoadingDetail(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator()
        Text("Loading inspection…", modifier = Modifier.padding(top = 12.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun MissingDetail(modifier: Modifier, message: String, onRetry: () -> Unit) {
    Column(
        modifier = modifier.fillMaxSize().padding(28.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Could not load inspection", style = MaterialTheme.typography.headlineMedium)
        Text(message, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 12.dp))
        Button(onClick = onRetry) { Text("Try again") }
    }
}
