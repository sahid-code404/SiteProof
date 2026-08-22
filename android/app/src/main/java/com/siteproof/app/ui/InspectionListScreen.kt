package com.siteproof.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.WorkOutline
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.siteproof.app.data.InspectionSummary
import com.siteproof.app.update.DevAppUpdateCard
import com.siteproof.app.update.DevAppUpdateManager
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private enum class InspectionFilter { ACTIVE, COMPLETED, ALL }

private fun formatDeadline(value: String): String = runCatching {
    OffsetDateTime.parse(value).format(DateTimeFormatter.ofPattern("dd MMM, hh:mm a", Locale.getDefault()))
}.getOrDefault(value)

private fun isFinished(status: String): Boolean = status in setOf("PROCESSING", "COMPLETED", "CANCELLED", "APPROVED", "REJECTED")

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
    var filter by rememberSaveable { mutableStateOf(InspectionFilter.ACTIVE) }
    var search by rememberSaveable { mutableStateOf("") }
    var accountOpen by rememberSaveable { mutableStateOf(false) }

    val activeCount = state.items.count { !isFinished(it.status) }
    val completedCount = state.items.count { isFinished(it.status) }
    val overdueCount = state.items.count { it.isOverdue && !isFinished(it.status) }
    val visible = state.items.filter { inspection ->
        val statusMatch = when (filter) {
            InspectionFilter.ACTIVE -> !isFinished(inspection.status)
            InspectionFilter.COMPLETED -> isFinished(inspection.status)
            InspectionFilter.ALL -> true
        }
        val query = search.trim().lowercase()
        val searchMatch = query.isBlank() || listOf(
            inspection.title,
            inspection.locationName.orEmpty(),
            inspection.locationAddress.orEmpty(),
            inspection.priority,
            inspection.status,
        ).any { it.lowercase().contains(query) }
        statusMatch && searchMatch
    }.sortedWith(compareBy<InspectionSummary> { isFinished(it.status) }.thenBy { it.deadline })

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                title = {
                    Column {
                        Text("SiteProof", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        Text(inspectorName, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                },
                actions = {
                    Box {
                        IconButton(onClick = { accountOpen = true }) {
                            Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer) {
                                Box(Modifier.size(38.dp), contentAlignment = Alignment.Center) {
                                    Text(inspectorName.trim().firstOrNull()?.uppercase() ?: "I", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                        DropdownMenu(expanded = accountOpen, onDismissRequest = { accountOpen = false }) {
                            DropdownMenuItem(
                                text = { Text("Sign out") },
                                leadingIcon = { Icon(Icons.Default.ExitToApp, contentDescription = null) },
                                onClick = { accountOpen = false; onSignOut() },
                            )
                        }
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
                else -> LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 36.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    item("summary") {
                        Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                            Text("My inspections", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                            Text(
                                when {
                                    overdueCount > 0 -> "$overdueCount overdue · $activeCount active"
                                    activeCount > 0 -> "$activeCount active assignment${if (activeCount == 1) "" else "s"}"
                                    else -> "No active work needs attention"
                                },
                                color = if (overdueCount > 0) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                    }

                    item("search") {
                        OutlinedTextField(
                            value = search,
                            onValueChange = { search = it },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            shape = RoundedCornerShape(16.dp),
                            placeholder = { Text("Search inspections") },
                            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedContainerColor = MaterialTheme.colorScheme.surface,
                                unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                                focusedBorderColor = MaterialTheme.colorScheme.primary,
                                unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant,
                            ),
                        )
                    }

                    item("tabs") {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                            FilterButton("Active", activeCount, filter == InspectionFilter.ACTIVE, Modifier.weight(1f)) { filter = InspectionFilter.ACTIVE }
                            FilterButton("Done", completedCount, filter == InspectionFilter.COMPLETED, Modifier.weight(1f)) { filter = InspectionFilter.COMPLETED }
                            FilterButton("All", state.items.size, filter == InspectionFilter.ALL, Modifier.weight(1f)) { filter = InspectionFilter.ALL }
                        }
                    }

                    if (state.offline) item("offline") { OfflineBanner() }
                    item("app-update") { DevAppUpdateCard(updateManager) }

                    if (!state.loading && visible.isEmpty()) {
                        item("empty") { EmptyState(hasQuery = search.isNotBlank(), filter = filter) }
                    } else {
                        items(visible, key = { it.id }) { inspection ->
                            InspectionCard(inspection = inspection, onClick = { onOpen(inspection.id) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun FilterButton(label: String, count: Int, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    Surface(
        modifier = modifier.clickable(onClick = onClick),
        shape = RoundedCornerShape(14.dp),
        color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface,
        border = if (selected) null else BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(Modifier.padding(vertical = 9.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(label, color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface, style = MaterialTheme.typography.labelLarge)
            Text(count.toString(), color = if (selected) MaterialTheme.colorScheme.onPrimary.copy(alpha = .8f) else MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun InspectionCard(inspection: InspectionSummary, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(15.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Surface(shape = RoundedCornerShape(15.dp), color = MaterialTheme.colorScheme.primaryContainer) {
                Box(Modifier.size(46.dp), contentAlignment = Alignment.Center) {
                    Icon(Icons.Default.WorkOutline, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                }
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(inspection.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    inspection.locationName ?: inspection.locationAddress ?: "${inspection.expectedLatitude}, ${inspection.expectedLongitude}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text("Due ${formatDeadline(inspection.deadline)}", style = MaterialTheme.typography.bodySmall, color = if (inspection.isOverdue) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(7.dp), verticalAlignment = Alignment.CenterVertically) {
                    StatusPill(inspection.status)
                    Text(inspection.priority.lowercase().replaceFirstChar { it.titlecase() }, color = priorityColor(inspection.priority), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
                }
            }
            Icon(Icons.Default.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun StatusPill(status: String) {
    val finished = isFinished(status)
    Surface(shape = RoundedCornerShape(999.dp), color = if (finished) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.primaryContainer) {
        Text(
            status.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() },
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            color = if (finished) MaterialTheme.colorScheme.onSecondaryContainer else MaterialTheme.colorScheme.onPrimaryContainer,
            style = MaterialTheme.typography.labelSmall,
        )
    }
}

@Composable
private fun OfflineBanner() {
    Surface(
        modifier = Modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite },
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.tertiaryContainer,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.tertiary.copy(alpha = .22f)),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text("Offline · showing last synced data", color = MaterialTheme.colorScheme.onTertiaryContainer, fontWeight = FontWeight.Bold)
            Text("Keep working with cached assignments. SiteProof will reconnect automatically.", color = MaterialTheme.colorScheme.onTertiaryContainer.copy(alpha = .8f), style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun EmptyState(hasQuery: Boolean, filter: InspectionFilter) {
    Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(if (hasQuery) "No matching inspections" else if (filter == InspectionFilter.ACTIVE) "Nothing needs action" else "No inspections here", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(if (hasQuery) "Try another search." else "New assignments will appear here when available.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ErrorState(message: String, onRetry: () -> Unit) {
    Box(Modifier.fillMaxSize().padding(18.dp).semantics { liveRegion = LiveRegionMode.Assertive }, contentAlignment = Alignment.Center) {
        Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = .28f))) {
            Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(11.dp)) {
                Text("Couldn't load inspections", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("Your saved data is safe. Check the connection and retry.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Surface(shape = RoundedCornerShape(12.dp), color = MaterialTheme.colorScheme.errorContainer) {
                    Text(message, Modifier.padding(11.dp), color = MaterialTheme.colorScheme.onErrorContainer, style = MaterialTheme.typography.bodySmall)
                }
                Button(onClick = onRetry, modifier = Modifier.fillMaxWidth().height(48.dp), shape = RoundedCornerShape(14.dp)) { Text("Try again") }
            }
        }
    }
}

@Composable
private fun priorityColor(priority: String) = when (priority) {
    "CRITICAL" -> MaterialTheme.colorScheme.error
    "HIGH" -> MaterialTheme.colorScheme.tertiary
    else -> MaterialTheme.colorScheme.primary
}
