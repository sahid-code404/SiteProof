package com.siteproof.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.siteproof.app.data.InspectionSummary
import com.siteproof.app.update.DevAppUpdateCard
import com.siteproof.app.update.DevAppUpdateManager
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private fun formatDeadline(value: String): String = runCatching {
    OffsetDateTime.parse(value).format(DateTimeFormatter.ofPattern("dd MMM, h:mm a", Locale.getDefault()))
}.getOrDefault(value)

private fun isFinished(status: String): Boolean = status in setOf("PROCESSING", "COMPLETED", "CANCELLED")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InspectionListScreen(
    inspectorName: String,
    state: InspectionsState,
    updateManager: DevAppUpdateManager,
    onRefresh: () -> Unit,
    onOpen: (String) -> Unit,
    onSignOut: () -> Unit,
) {
    var showCompleted by rememberSaveable { mutableStateOf(false) }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Inspections")
                        Text(
                            inspectorName,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = onSignOut) {
                        Icon(Icons.Default.ExitToApp, contentDescription = "Sign out")
                    }
                },
            )
        },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = state.loading,
            onRefresh = onRefresh,
            modifier = Modifier.padding(padding).fillMaxSize(),
        ) {
            when {
                state.error != null -> ErrorState(message = state.error, onRetry = onRefresh)
                !state.loading && state.items.isEmpty() -> EmptyState()
                else -> {
                    val active = state.items.filterNot { isFinished(it.status) }
                    val completed = state.items.filter { isFinished(it.status) }.sortedByDescending { it.updatedAt }

                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 28.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        item(key = "app-update") { DevAppUpdateCard(updateManager) }

                        if (state.offline) {
                            item(key = "offline") { OfflineBanner() }
                        }

                        item(key = "active-heading") {
                            SectionHeading("Active", "${active.size} inspection${if (active.size == 1) "" else "s"}")
                        }

                        if (active.isEmpty()) {
                            item(key = "active-empty") {
                                Surface(
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(12.dp),
                                    color = MaterialTheme.colorScheme.surface,
                                ) {
                                    Text(
                                        "Nothing needs action right now.",
                                        modifier = Modifier.padding(18.dp),
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        } else {
                            items(active, key = { it.id }) { inspection ->
                                InspectionCard(inspection = inspection, onClick = { onOpen(inspection.id) })
                            }
                        }

                        if (completed.isNotEmpty()) {
                            item(key = "completed-toggle") {
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    SectionHeading("Completed", "${completed.size} saved")
                                    TextButton(onClick = { showCompleted = !showCompleted }) {
                                        Text(if (showCompleted) "Hide" else "Show")
                                    }
                                }
                            }

                            if (showCompleted) {
                                items(completed, key = { "completed-${it.id}" }) { inspection ->
                                    InspectionCard(inspection = inspection, onClick = { onOpen(inspection.id) })
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun OfflineBanner() {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics { liveRegion = LiveRegionMode.Polite },
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.tertiary.copy(alpha = 0.10f),
    ) {
        Column(Modifier.padding(14.dp)) {
            Text("Offline", fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.tertiary)
            Text(
                "Showing the last synced copy. Pull to refresh when you're back online.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun SectionHeading(title: String, subtitle: String) {
    Column(modifier = Modifier.padding(top = 4.dp, bottom = 2.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun InspectionCard(inspection: InspectionSummary, onClick: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StatusPill(inspection.status)
                Text(
                    inspection.priority.lowercase().replaceFirstChar { it.titlecase() },
                    style = MaterialTheme.typography.labelLarge,
                    color = priorityColor(inspection.priority),
                )
            }

            Text(inspection.title, style = MaterialTheme.typography.titleLarge)
            Text(
                inspection.locationName ?: inspection.locationAddress ?: "${inspection.expectedLatitude}, ${inspection.expectedLongitude}",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(Modifier.height(2.dp))
            Text("Due ${formatDeadline(inspection.deadline)}", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun StatusPill(status: String) {
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = MaterialTheme.colorScheme.primaryContainer,
    ) {
        Text(
            status.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() },
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onPrimaryContainer,
        )
    }
}

@Composable
private fun EmptyState() {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.Start,
    ) {
        Text("No inspections yet", style = MaterialTheme.typography.headlineMedium)
        Text("New assignments will appear here.", color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ErrorState(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp)
            .semantics { liveRegion = LiveRegionMode.Assertive },
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Could not load inspections", style = MaterialTheme.typography.headlineMedium)
        Text(message, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 12.dp))
        Button(onClick = onRetry) { Text("Try again") }
    }
}

@Composable
private fun priorityColor(priority: String) = when (priority) {
    "CRITICAL" -> MaterialTheme.colorScheme.error
    "HIGH" -> MaterialTheme.colorScheme.tertiary
    else -> MaterialTheme.colorScheme.primary
}
