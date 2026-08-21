package com.siteproof.app.ui

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private fun detailDeadline(value: String): String = runCatching {
    OffsetDateTime.parse(value).format(DateTimeFormatter.ofPattern("dd MMM yyyy, h:mm a", Locale.getDefault()))
}.getOrDefault(value)

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
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(SiteProofOrangeGradient)
                    .statusBarsPadding()
                    .height(68.dp)
                    .padding(horizontal = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack, modifier = Modifier.background(Color.White.copy(alpha = 0.12f), CircleShape)) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Color.White)
                }
                Text("Inspection", modifier = Modifier.padding(start = 12.dp), style = MaterialTheme.typography.titleLarge, color = Color.White, fontWeight = FontWeight.Bold)
            }
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
                        .padding(horizontal = 16.dp, vertical = 16.dp)
                        .animateContentSize(),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    if (state.offline) {
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(14.dp),
                            color = MaterialTheme.colorScheme.tertiaryContainer,
                        ) {
                            Column(Modifier.padding(14.dp)) {
                                Text("Offline", color = MaterialTheme.colorScheme.onTertiaryContainer, fontWeight = FontWeight.SemiBold)
                                Text("Showing the last synced copy.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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

                    ReferenceCard {
                        DetailField("Location", item.locationName ?: item.locationAddress ?: "${item.expectedLatitude}, ${item.expectedLongitude}")
                        DetailField("Capture area", "Within ${item.allowedRadiusMeters} m")
                        DetailField("Deadline", detailDeadline(item.deadline))
                        DetailField("Type", item.inspectionType.replace('_', ' '))
                    }

                    ReferenceCard {
                        Text("Instructions", style = MaterialTheme.typography.titleMedium)
                        Text(item.instructions ?: "No additional instructions.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }

                    state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }

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
private fun ReferenceCard(content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().shadow(6.dp, RoundedCornerShape(16.dp)),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Column(Modifier.padding(17.dp), verticalArrangement = Arrangement.spacedBy(14.dp), content = content)
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
        "ASSIGNED" -> Button(onClick = onAcknowledge, enabled = !actionInProgress && !offline, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text(if (actionInProgress) "Updating…" else "Acknowledge") }
        "ACKNOWLEDGED" -> Button(onClick = onReady, enabled = !actionInProgress && !offline, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text(if (actionInProgress) "Updating…" else "Mark ready") }
        "READY" -> Button(onClick = onStartVerification, enabled = !offline, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text("Start verification") }
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
    Surface(shape = RoundedCornerShape(8.dp), color = MaterialTheme.colorScheme.primaryContainer) {
        Text(value.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() }, modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
    }
}

@Composable
private fun StatusMessage(message: String) {
    Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp), color = MaterialTheme.colorScheme.primaryContainer) {
        Text(message, modifier = Modifier.padding(14.dp), color = MaterialTheme.colorScheme.onPrimaryContainer)
    }
}

@Composable
private fun LoadingDetail(modifier: Modifier = Modifier) {
    Column(modifier = modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        CircularProgressIndicator()
        Text("Loading inspection…", modifier = Modifier.padding(top = 12.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun MissingDetail(modifier: Modifier, message: String, onRetry: () -> Unit) {
    Column(modifier = modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.Center) {
        Text("Could not load inspection", style = MaterialTheme.typography.headlineMedium)
        Text(message, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 12.dp))
        Button(onClick = onRetry) { Text("Try again") }
    }
}
