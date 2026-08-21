package com.siteproof.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
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
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material.icons.filled.NotificationsNone
import androidx.compose.material.icons.filled.Person
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
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
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
    OffsetDateTime.parse(value).format(DateTimeFormatter.ofPattern("dd MMM yyyy, hh:mm a", Locale.getDefault()))
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
            AdaptiveHeader(
                inspectorName = inspectorName,
                activeCount = activeCount,
                overdueCount = overdueCount,
                onSignOut = onSignOut,
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
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 20.dp, bottom = 38.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item(key = "title") {
                        Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            Text("My inspections", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                            Text(
                                when {
                                    overdueCount > 0 -> "$overdueCount need attention · $activeCount active"
                                    activeCount > 0 -> "$activeCount active assignment${if (activeCount == 1) "" else "s"}"
                                    else -> "No active work needs attention",
                                },
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                    }
                    item(key = "search") {
                        OutlinedTextField(
                            value = search,
                            onValueChange = { search = it },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            shape = RoundedCornerShape(16.dp),
                            placeholder = { Text("Search site, status or priority") },
                            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = MaterialTheme.colorScheme.primary,
                                unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant,
                                focusedContainerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f),
                                unfocusedContainerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.78f),
                            ),
                        )
                    }
                    item(key = "tabs") {
                        InspectionTabs(
                            filter = filter,
                            activeCount = activeCount,
                            completedCount = completedCount,
                            totalCount = state.items.size,
                            onFilter = { filter = it },
                        )
                    }
                    item(key = "app-update") { DevAppUpdateCard(updateManager) }
                    if (state.offline) item(key = "offline") { OfflineBanner() }

                    if (!state.loading && visible.isEmpty()) {
                        item(key = "empty") { EmptyState(filter = filter, hasQuery = search.isNotBlank()) }
                    } else {
                        items(visible, key = { it.id }) { inspection ->
                            InspectionCard(inspection = inspection, onClick = { onOpen(inspection.id) })
                        }
                    }

                    if (!state.loading && !state.offline && visible.isNotEmpty()) {
                        item(key = "sync-state") { SyncedCard() }
                    }
                }
            }
        }
    }
}

@Composable
private fun AdaptiveHeader(
    inspectorName: String,
    activeCount: Int,
    overdueCount: Int,
    onSignOut: () -> Unit,
) {
    var notificationsOpen by remember { mutableStateOf(false) }
    var accountOpen by remember { mutableStateOf(false) }
    val scheme = MaterialTheme.colorScheme

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                Brush.linearGradient(
                    listOf(
                        scheme.surface,
                        scheme.surfaceVariant.copy(alpha = 0.92f),
                    ),
                ),
            )
            .statusBarsPadding()
            .height(108.dp),
    ) {
        Box(
            modifier = Modifier
                .size(118.dp)
                .align(Alignment.TopEnd)
                .blur(34.dp)
                .background(scheme.primary.copy(alpha = 0.24f), CircleShape),
        )
        Box(
            modifier = Modifier
                .size(92.dp)
                .align(Alignment.BottomStart)
                .blur(30.dp)
                .background(scheme.primary.copy(alpha = 0.12f), CircleShape),
        )

        Row(
            modifier = Modifier.fillMaxSize().padding(horizontal = 18.dp, vertical = 15.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("SiteProof", style = MaterialTheme.typography.titleLarge, color = scheme.onSurface, fontWeight = FontWeight.Bold)
                Text("Field verification", style = MaterialTheme.typography.bodyMedium, color = scheme.primary, fontWeight = FontWeight.SemiBold)
                Text(inspectorName, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant, modifier = Modifier.padding(top = 2.dp))
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Box {
                    IconButton(
                        onClick = { notificationsOpen = !notificationsOpen; accountOpen = false },
                        modifier = Modifier.background(scheme.surface.copy(alpha = 0.7f), CircleShape),
                    ) {
                        Icon(Icons.Default.NotificationsNone, contentDescription = "Notifications", tint = scheme.onSurface)
                    }
                    if (overdueCount > 0) {
                        Surface(
                            modifier = Modifier.align(Alignment.TopEnd).size(19.dp),
                            shape = CircleShape,
                            color = scheme.error,
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Text(overdueCount.coerceAtMost(9).toString(), color = scheme.onError, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                    DropdownMenu(expanded = notificationsOpen, onDismissRequest = { notificationsOpen = false }) {
                        DropdownMenuItem(
                            text = {
                                Column {
                                    Text("Notifications", fontWeight = FontWeight.Bold)
                                    Text("Live assignment status", style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
                                }
                            },
                            onClick = {},
                            enabled = false,
                        )
                        if (overdueCount > 0) {
                            DropdownMenuItem(
                                text = { Text("$overdueCount overdue inspection${if (overdueCount == 1) "" else "s"}") },
                                onClick = { notificationsOpen = false },
                            )
                        }
                        DropdownMenuItem(
                            text = { Text("$activeCount active inspection${if (activeCount == 1) "" else "s"}") },
                            onClick = { notificationsOpen = false },
                        )
                        if (overdueCount == 0 && activeCount == 0) {
                            DropdownMenuItem(text = { Text("You're all set") }, onClick = { notificationsOpen = false })
                        }
                    }
                }

                Box {
                    Surface(
                        modifier = Modifier.size(44.dp).clickable { accountOpen = !accountOpen; notificationsOpen = false },
                        shape = CircleShape,
                        color = scheme.primaryContainer,
                        border = BorderStroke(1.dp, scheme.primary.copy(alpha = 0.2f)),
                        shadowElevation = 4.dp,
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Text(
                                inspectorName.trim().firstOrNull()?.uppercase() ?: "I",
                                color = scheme.primary,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                    DropdownMenu(expanded = accountOpen, onDismissRequest = { accountOpen = false }) {
                        DropdownMenuItem(
                            leadingIcon = { Icon(Icons.Default.Person, contentDescription = null) },
                            text = {
                                Column {
                                    Text(inspectorName, fontWeight = FontWeight.Bold)
                                    Text("Inspector account", style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
                                }
                            },
                            onClick = {},
                            enabled = false,
                        )
                        DropdownMenuItem(
                            leadingIcon = { Icon(Icons.Default.ExitToApp, contentDescription = null) },
                            text = { Text("Sign out") },
                            onClick = { accountOpen = false; onSignOut() },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun InspectionTabs(
    filter: InspectionFilter,
    activeCount: Int,
    completedCount: Int,
    totalCount: Int,
    onFilter: (InspectionFilter) -> Unit,
) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChipButton("Active ($activeCount)", filter == InspectionFilter.ACTIVE, Modifier.weight(1f)) { onFilter(InspectionFilter.ACTIVE) }
        FilterChipButton("Done ($completedCount)", filter == InspectionFilter.COMPLETED, Modifier.weight(1f)) { onFilter(InspectionFilter.COMPLETED) }
        FilterChipButton("All ($totalCount)", filter == InspectionFilter.ALL, Modifier.weight(1f)) { onFilter(InspectionFilter.ALL) }
    }
}

@Composable
private fun FilterChipButton(label: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        modifier = modifier.clickable(onClick = onClick),
        shape = RoundedCornerShape(13.dp),
        color = if (selected) scheme.primary else scheme.surface.copy(alpha = 0.78f),
        border = if (selected) null else BorderStroke(1.dp, scheme.outlineVariant),
        shadowElevation = if (selected) 5.dp else 0.dp,
    ) {
        Box(modifier = Modifier.padding(horizontal = 7.dp, vertical = 10.dp), contentAlignment = Alignment.Center) {
            Text(label, style = MaterialTheme.typography.labelLarge, color = if (selected) scheme.onPrimary else scheme.onSurface, maxLines = 1)
        }
    }
}

@Composable
private fun OfflineBanner() {
    Surface(
        modifier = Modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite },
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.tertiaryContainer,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.tertiary.copy(alpha = 0.18f)),
    ) {
        Column(Modifier.padding(15.dp)) {
            Text("Offline · cached data", fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onTertiaryContainer)
            Text("You can keep reviewing the last synced assignments. SiteProof will reconnect when a network is available.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onTertiaryContainer.copy(alpha = 0.78f))
        }
    }
}

@Composable
private fun InspectionCard(inspection: InspectionSummary, onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Card(
        modifier = Modifier.fillMaxWidth().animateContentSize().shadow(4.dp, RoundedCornerShape(20.dp)).clickable(onClick = onClick),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = scheme.surface.copy(alpha = 0.92f)),
        border = BorderStroke(1.dp, scheme.outlineVariant),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp, pressedElevation = 2.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(13.dp),
        ) {
            Surface(
                modifier = Modifier.size(48.dp),
                shape = RoundedCornerShape(15.dp),
                color = scheme.primaryContainer,
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(Icons.Default.WorkOutline, contentDescription = null, tint = scheme.primary, modifier = Modifier.size(24.dp))
                }
            }
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(inspection.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    inspection.locationName ?: inspection.locationAddress ?: "${inspection.expectedLatitude}, ${inspection.expectedLongitude}",
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text("Due ${formatDeadline(inspection.deadline)}", style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    StatusPill(inspection.status)
                    Text(inspection.priority.lowercase().replaceFirstChar { it.titlecase() }, style = MaterialTheme.typography.labelMedium, color = priorityColor(inspection.priority))
                }
            }
            Icon(Icons.Default.ChevronRight, contentDescription = null, tint = scheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun StatusPill(status: String) {
    val scheme = MaterialTheme.colorScheme
    val finished = isFinished(status)
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = if (finished) scheme.secondaryContainer else scheme.primaryContainer,
    ) {
        Text(
            status.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() },
            modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelSmall,
            color = if (finished) scheme.onSecondaryContainer else scheme.onPrimaryContainer,
        )
    }
}

@Composable
private fun SyncedCard() {
    AnimatedVisibility(visible = true, enter = fadeIn() + slideInVertically { it / 3 }, exit = fadeOut() + slideOutVertically { it / 3 }) {
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.66f),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)),
        ) {
            Row(modifier = Modifier.padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("Synced and ready", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("No pending uploads", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Surface(modifier = Modifier.size(44.dp), shape = CircleShape, color = MaterialTheme.colorScheme.primary.copy(alpha = 0.13f)) {
                    Box(contentAlignment = Alignment.Center) { Text("✓", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold) }
                }
            }
        }
    }
}

@Composable
private fun EmptyState(filter: InspectionFilter, hasQuery: Boolean) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.84f),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(modifier = Modifier.padding(24.dp), horizontalAlignment = Alignment.Start) {
            Text(
                if (hasQuery) "No matching inspections" else if (filter == InspectionFilter.ACTIVE) "Nothing needs action" else "No inspections here",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Text(if (hasQuery) "Try a different site, status or priority." else "New assignments will appear here automatically.", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 5.dp))
        }
    }
}

@Composable
private fun ErrorState(message: String, onRetry: () -> Unit) {
    Box(modifier = Modifier.fillMaxSize().padding(22.dp).semantics { liveRegion = LiveRegionMode.Assertive }, contentAlignment = Alignment.Center) {
        Surface(
            shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.surface,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.2f)),
        ) {
            Column(modifier = Modifier.fillMaxWidth().padding(22.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Inspections couldn't be refreshed", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("Your last synced data is kept on this device. Check the connection and retry.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                Button(onClick = onRetry, modifier = Modifier.fillMaxWidth()) { Text("Try again") }
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
