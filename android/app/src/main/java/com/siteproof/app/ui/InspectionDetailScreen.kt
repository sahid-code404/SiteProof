package com.siteproof.app.ui

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
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
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
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
        topBar = { AdaptiveDetailHeader(onBack) },
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
                        .padding(horizontal = 16.dp, vertical = 18.dp)
                        .animateContentSize(),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    if (state.offline) {
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(18.dp),
                            color = MaterialTheme.colorScheme.tertiaryContainer,
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.tertiary.copy(alpha = 0.18f)),
                        ) {
                            Column(Modifier.padding(15.dp)) {
                                Text("Offline · cached inspection", color = MaterialTheme.colorScheme.onTertiaryContainer, fontWeight = FontWeight.SemiBold)
                                Text("You can review this assignment now; online actions will resume after reconnection.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onTertiaryContainer.copy(alpha = 0.78f))
                            }
                        }
                    }

                    Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                        Text(item.title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                        Text(
                            item.locationName ?: item.locationAddress ?: "Assigned field location",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            DetailChip(item.status)
                            DetailChip(item.priority)
                        }
                    }

                    AdaptiveCard {
                        Text("Capture requirements", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        DetailField("Location", item.locationName ?: item.locationAddress ?: "${item.expectedLatitude}, ${item.expectedLongitude}")
                        DetailField("Capture radius", "Within ${item.allowedRadiusMeters} m")
                        DetailField("Minimum evidence video", videoLengthLabel(item.captureDurationSeconds))
                        DetailField("Deadline", detailDeadline(item.deadline))
                        DetailField("Inspection type", item.inspectionType.replace('_', ' '))
                    }

                    AdaptiveCard {
                        Text("Instructions", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(item.instructions ?: "No additional instructions.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }

                    state.error?.let {
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            color = MaterialTheme.colorScheme.errorContainer,
                        ) {
                            Text(it, color = MaterialTheme.colorScheme.onErrorContainer, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(14.dp))
                        }
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
                        StatusMessage("Live verification is in progress. Keep SiteProof open until capture is complete.")
                    } else if (item.status == "PROCESSING") {
                        StatusMessage("Evidence uploaded successfully. Verification is processing.")
                    }
                    Spacer(Modifier.height(8.dp))
                }
            }
        }
    }
}

@Composable
private fun AdaptiveDetailHeader(onBack: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(Brush.linearGradient(listOf(scheme.surface, scheme.surfaceVariant)))
            .statusBarsPadding()
            .height(72.dp),
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.CenterEnd)
                .padding(end = 8.dp)
                .fillMaxWidth(0.34f)
                .height(72.dp)
                .blur(28.dp)
                .background(scheme.primary.copy(alpha = 0.16f)),
        )
        Row(
            modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack, modifier = Modifier.background(scheme.surface.copy(alpha = 0.76f), CircleShape)) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = scheme.onSurface)
            }
            Column(modifier = Modifier.padding(start = 12.dp)) {
                Text("Inspection", style = MaterialTheme.typography.titleLarge, color = scheme.onSurface, fontWeight = FontWeight.Bold)
                Text("Field assignment", style = MaterialTheme.typography.bodySmall, color = scheme.primary)
            }
        }
    }
}

@Composable
private fun AdaptiveCard(content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.9f)),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp), content = content)
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
    val shape = RoundedCornerShape(16.dp)
    when (status) {
        "ASSIGNED" -> Button(onClick = onAcknowledge, enabled = !actionInProgress && !offline, modifier = Modifier.fillMaxWidth().height(54.dp), shape = shape) { Text(if (actionInProgress) "Updating…" else "Acknowledge assignment") }
        "ACKNOWLEDGED" -> Button(onClick = onReady, enabled = !actionInProgress && !offline, modifier = Modifier.fillMaxWidth().height(54.dp), shape = shape) { Text(if (actionInProgress) "Updating…" else "I'm ready to capture") }
        "READY" -> Button(onClick = onStartVerification, enabled = !offline, modifier = Modifier.fillMaxWidth().height(56.dp), shape = shape) { Text("Start live verification") }
    }
}

@Composable
private fun DetailField(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun DetailChip(value: String) {
    val normalized = value.uppercase()
    val scheme = MaterialTheme.colorScheme
    val (background, foreground) = when {
        normalized in setOf("READY", "APPROVED") -> scheme.primaryContainer to scheme.onPrimaryContainer
        normalized in setOf("REJECTED", "CANCELLED", "CRITICAL") -> scheme.errorContainer to scheme.onErrorContainer
        normalized in setOf("HIGH", "PROCESSING", "EVIDENCE_UPLOADING") -> scheme.tertiaryContainer to scheme.onTertiaryContainer
        normalized in setOf("ASSIGNED", "ACKNOWLEDGED") -> scheme.secondaryContainer to scheme.onSecondaryContainer
        else -> scheme.surfaceVariant to scheme.onSurfaceVariant
    }
    Surface(shape = RoundedCornerShape(999.dp), color = background) {
        Text(
            value.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() },
            modifier = Modifier.padding(horizontal = 11.dp, vertical = 6.dp),
            style = MaterialTheme.typography.labelLarge,
            color = foreground,
        )
    }
}

@Composable
private fun StatusMessage(message: String) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.74f),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.14f)),
    ) {
        Text(message, modifier = Modifier.padding(15.dp), color = MaterialTheme.colorScheme.onPrimaryContainer)
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
    Box(modifier = modifier.fillMaxSize().padding(22.dp), contentAlignment = Alignment.Center) {
        Surface(
            shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.surface,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.2f)),
        ) {
            Column(modifier = Modifier.fillMaxWidth().padding(22.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Inspection unavailable", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("The assignment could not be loaded. Your cached work has not been removed.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                Button(onClick = onRetry, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) { Text("Try again") }
            }
        }
    }
}
