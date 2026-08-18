package com.siteproof.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.siteproof.app.data.InspectionSummary
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private fun formatDeadline(value: String): String = runCatching {
    OffsetDateTime.parse(value).format(DateTimeFormatter.ofPattern("dd MMM, h:mm a", Locale.getDefault()))
}.getOrDefault(value)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InspectionListScreen(
    inspectorName: String,
    state: InspectionsState,
    onRefresh: () -> Unit,
    onOpen: (String) -> Unit,
    onSignOut: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("My Inspections")
                        Text(inspectorName, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                else -> LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    if (state.offline) {
                        item {
                            Text(
                                "Offline — showing last synced data",
                                color = MaterialTheme.colorScheme.tertiary,
                                style = MaterialTheme.typography.labelLarge,
                                modifier = Modifier.padding(bottom = 4.dp),
                            )
                        }
                    }
                    items(state.items, key = { it.id }) { inspection ->
                        InspectionCard(inspection = inspection, onClick = { onOpen(inspection.id) })
                    }
                }
            }
        }
    }
}

@Composable
private fun InspectionCard(inspection: InspectionSummary, onClick: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(inspection.priority, style = MaterialTheme.typography.labelLarge, color = priorityColor(inspection.priority))
                Text(inspection.status, style = MaterialTheme.typography.labelMedium)
            }
            Spacer(Modifier.height(10.dp))
            Text(inspection.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            Text(
                inspection.locationName ?: inspection.locationAddress ?: "${inspection.expectedLatitude}, ${inspection.expectedLongitude}",
                modifier = Modifier.padding(top = 7.dp),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))
            Text("Deadline", style = MaterialTheme.typography.labelSmall)
            Text(formatDeadline(inspection.deadline), style = MaterialTheme.typography.bodyMedium)
            Text(
                "Distance unavailable",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }
}

@Composable
private fun EmptyState() {
    Column(modifier = Modifier.fillMaxSize().padding(32.dp), verticalArrangement = Arrangement.Center) {
        Text("No inspections assigned.", style = MaterialTheme.typography.headlineSmall)
        Text("New assignments will appear here.", color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ErrorState(message: String, onRetry: () -> Unit) {
    Column(modifier = Modifier.fillMaxSize().padding(32.dp), verticalArrangement = Arrangement.Center) {
        Text("Unable to load inspections.", style = MaterialTheme.typography.headlineSmall)
        Text(message, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 12.dp))
        Button(onClick = onRetry) { Text("Retry") }
    }
}

@Composable
private fun priorityColor(priority: String) = when (priority) {
    "CRITICAL" -> MaterialTheme.colorScheme.error
    "HIGH" -> MaterialTheme.colorScheme.tertiary
    else -> MaterialTheme.colorScheme.primary
}
