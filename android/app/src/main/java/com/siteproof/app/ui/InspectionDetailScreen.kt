package com.siteproof.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
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
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
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

private fun videoLengthLabel(seconds: Int): String = when {
    seconds >= 120 && seconds % 60 == 0 -> "${seconds / 60} minutes"
    seconds >= 60 -> "${seconds / 60} min ${seconds % 60} sec"
    else -> "$seconds seconds"
}

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
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") } },
                title = { Column { Text("Inspection", fontWeight = FontWeight.Bold); Text("Field assignment", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) } },
            )
        },
    ) { padding ->
        when {
            state.loading -> LoadingDetail(Modifier.padding(padding))
            state.item == null -> MissingDetail(Modifier.padding(padding), state.error ?: "Inspection not found.", onRetry)
            else -> {
                val item = state.item
                Column(
                    modifier = Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    if (state.offline) OfflineDetailBanner()

                    Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
                        Text(item.title, style = MaterialTheme.typography.headlineMedium)
                        Text(item.locationName ?: item.locationAddress ?: "Assigned field location", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) { DetailChip(item.status); DetailChip(item.priority) }
                    }

                    IndustrialCard {
                        Text("Capture requirements", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        DetailField("Location", item.locationName ?: item.locationAddress ?: "${item.expectedLatitude}, ${item.expectedLongitude}")
                        DetailField("Allowed radius", "${item.allowedRadiusMeters} m")
                        DetailField("Minimum video", videoLengthLabel(item.captureDurationSeconds))
                        DetailField("Deadline", detailDeadline(item.deadline))
                        DetailField("Type", item.inspectionType.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() })
                    }

                    IndustrialCard {
                        Text("Instructions", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(item.instructions ?: "No additional instructions.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }

                    state.error?.let { message ->
                        Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.errorContainer, border = BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = .24f))) {
                            Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text("Action failed", color = MaterialTheme.colorScheme.onErrorContainer, fontWeight = FontWeight.Bold)
                                Text(message, color = MaterialTheme.colorScheme.onErrorContainer, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }

                    InspectionAction(item.status, state.actionInProgress, state.offline, onAcknowledge, onReady, onStartVerification)

                    when (item.status) {
                        "SESSION_STARTED", "EVIDENCE_UPLOADING" -> StatusMessage("Verification is active. Keep SiteProof open until capture and upload finish.")
                        "PROCESSING" -> StatusMessage("Evidence uploaded. Verification processing is underway.")
                    }
                    Spacer(Modifier.height(10.dp))
                }
            }
        }
    }
}

@Composable
private fun IndustrialCard(content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(17.dp), verticalArrangement = Arrangement.spacedBy(13.dp), content = content)
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
    val modifier = Modifier.fillMaxWidth().height(52.dp)
    val shape = RoundedCornerShape(15.dp)
    when (status) {
        "ASSIGNED" -> Button(onClick = onAcknowledge, enabled = !actionInProgress && !offline, modifier = modifier, shape = shape) { Text(if (actionInProgress) "Updating…" else "Acknowledge assignment") }
        "ACKNOWLEDGED" -> Button(onClick = onReady, enabled = !actionInProgress && !offline, modifier = modifier, shape = shape) { Text(if (actionInProgress) "Updating…" else "Ready to capture") }
        "READY" -> Button(onClick = onStartVerification, enabled = !offline, modifier = modifier, shape = shape) { Text("Start verification") }
    }
}

@Composable
private fun DetailField(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(label.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun DetailChip(value: String) {
    val normalized = value.uppercase()
    val scheme = MaterialTheme.colorScheme
    val pair = when {
        normalized in setOf("READY", "APPROVED") -> scheme.primaryContainer to scheme.onPrimaryContainer
        normalized in setOf("REJECTED", "CANCELLED", "CRITICAL") -> scheme.errorContainer to scheme.onErrorContainer
        normalized in setOf("HIGH", "PROCESSING", "EVIDENCE_UPLOADING") -> scheme.tertiaryContainer to scheme.onTertiaryContainer
        normalized in setOf("ASSIGNED", "ACKNOWLEDGED") -> scheme.secondaryContainer to scheme.onSecondaryContainer
        else -> scheme.surfaceVariant to scheme.onSurfaceVariant
    }
    Surface(shape = RoundedCornerShape(999.dp), color = pair.first) {
        Text(value.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() }, Modifier.padding(horizontal = 10.dp, vertical = 5.dp), color = pair.second, style = MaterialTheme.typography.labelMedium)
    }
}

@Composable
private fun OfflineDetailBanner() {
    Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.tertiaryContainer, border = BorderStroke(1.dp, MaterialTheme.colorScheme.tertiary.copy(alpha = .22f))) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("Offline · cached inspection", color = MaterialTheme.colorScheme.onTertiaryContainer, fontWeight = FontWeight.Bold)
            Text("Review is available. Online actions resume after reconnection.", color = MaterialTheme.colorScheme.onTertiaryContainer.copy(alpha = .8f), style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun StatusMessage(message: String) {
    Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.primaryContainer, border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = .2f))) {
        Text(message, Modifier.padding(14.dp), color = MaterialTheme.colorScheme.onPrimaryContainer)
    }
}

@Composable
private fun LoadingDetail(modifier: Modifier = Modifier) {
    Column(modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        CircularProgressIndicator()
        Text("Loading inspection…", Modifier.padding(top = 11.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun MissingDetail(modifier: Modifier, message: String, onRetry: () -> Unit) {
    Box(modifier.fillMaxSize().padding(18.dp), contentAlignment = Alignment.Center) {
        Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = .28f))) {
            Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Inspection unavailable", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("The assignment could not be loaded. Cached work has not been removed.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Surface(shape = RoundedCornerShape(12.dp), color = MaterialTheme.colorScheme.errorContainer) { Text(message, Modifier.padding(10.dp), color = MaterialTheme.colorScheme.onErrorContainer, style = MaterialTheme.typography.bodySmall) }
                Button(onClick = onRetry, modifier = Modifier.fillMaxWidth().height(48.dp), shape = RoundedCornerShape(14.dp)) { Text("Try again") }
            }
        }
    }
}
