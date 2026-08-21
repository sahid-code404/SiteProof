package com.siteproof.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
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
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.WorkOutline
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
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
        topBar = { ReferenceHeader(inspectorName = inspectorName, onSignOut = onSignOut) },
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
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 18.dp, bottom = 34.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item(key = "title") {
                        Text("My Inspections", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    }
                    item(key = "search") {
                        OutlinedTextField(
                            value = search,
                            onValueChange = { search = it },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            shape = RoundedCornerShape(12.dp),
                            placeholder = { Text("Search inspections") },
                            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = MaterialTheme.colorScheme.primary,
                                unfocusedBorderColor = MaterialTheme.colorScheme.outline,
                                focusedContainerColor = Color.White,
                                unfocusedContainerColor = Color.White,
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
private fun ReferenceHeader(inspectorName: String, onSignOut: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                Brush.linearGradient(
                    listOf(Color(0xFFFF9827), Color(0xFFFF6900), Color(0xFFF04C00)),
                ),
            )
            .statusBarsPadding()
            .height(112.dp)
            .clip(RoundedCornerShape(bottomStart = 0.dp, bottomEnd = 0.dp)),
    ) {
        Box(
            modifier = Modifier
                .size(96.dp)
                .align(Alignment.TopEnd)
                .padding(top = 4.dp, end = 16.dp)
                .blur(24.dp)
                .background(Color.White.copy(alpha = 0.18f), CircleShape),
        )
        Box(
            modifier = Modifier
                .size(70.dp)
                .align(Alignment.BottomStart)
                .padding(start = 12.dp)
                .blur(20.dp)
                .background(Color(0xFFFFC27A).copy(alpha = 0.25f), CircleShape),
        )
        Row(
            modifier = Modifier.fillMaxSize().padding(horizontal = 18.dp, vertical = 17.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("SiteProof", style = MaterialTheme.typography.titleLarge, color = Color.White, fontWeight = FontWeight.Bold)
                Text("Field Verification", style = MaterialTheme.typography.bodyMedium, color = Color.White.copy(alpha = 0.9f))
                Text(inspectorName, style = MaterialTheme.typography.bodySmall, color = Color.White.copy(alpha = 0.75f), modifier = Modifier.padding(top = 2.dp))
            }
            IconButton(
                onClick = onSignOut,
                modifier = Modifier.background(Color.White.copy(alpha = 0.12f), CircleShape),
            ) {
                Icon(Icons.Default.ExitToApp, contentDescription = "Sign out", tint = Color.White)
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
        FilterChipButton("Completed ($completedCount)", filter == InspectionFilter.COMPLETED, Modifier.weight(1f)) { onFilter(InspectionFilter.COMPLETED) }
        FilterChipButton("All ($totalCount)", filter == InspectionFilter.ALL, Modifier.weight(1f)) { onFilter(InspectionFilter.ALL) }
    }
}

@Composable
private fun FilterChipButton(label: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Surface(
        modifier = modifier
            .shadow(if (selected) 6.dp else 1.dp, RoundedCornerShape(11.dp))
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(11.dp),
        color = if (selected) MaterialTheme.colorScheme.primary else Color.White,
        border = if (selected) null else androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Box(modifier = Modifier.padding(horizontal = 8.dp, vertical = 10.dp), contentAlignment = Alignment.Center) {
            Text(
                label,
                style = MaterialTheme.typography.labelLarge,
                color = if (selected) Color.White else MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
            )
        }
    }
}

@Composable
private fun OfflineBanner() {
    Surface(
        modifier = Modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite },
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.tertiaryContainer,
    ) {
        Column(Modifier.padding(14.dp)) {
            Text("Offline", fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onTertiaryContainer)
            Text("Showing the last synced copy. Pull to refresh when you're back online.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun InspectionCard(inspection: InspectionSummary, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .animateContentSize()
            .shadow(7.dp, RoundedCornerShape(16.dp))
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp, pressedElevation = 2.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Surface(
                modifier = Modifier.size(46.dp),
                shape = CircleShape,
                color = MaterialTheme.colorScheme.primaryContainer,
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(Icons.Default.WorkOutline, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(24.dp))
                }
            }
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(inspection.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(inspection.locationName ?: inspection.locationAddress ?: "${inspection.expectedLatitude}, ${inspection.expectedLongitude}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text("Due: ${formatDeadline(inspection.deadline)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    StatusPill(inspection.status)
                    Text(inspection.priority.lowercase().replaceFirstChar { it.titlecase() }, style = MaterialTheme.typography.labelMedium, color = priorityColor(inspection.priority))
                }
            }
            Icon(Icons.Default.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun StatusPill(status: String) {
    val finished = isFinished(status)
    Surface(
        shape = RoundedCornerShape(7.dp),
        color = if (finished) Color(0xFFEAF2FF) else MaterialTheme.colorScheme.primaryContainer,
    ) {
        Text(
            status.replace('_', ' ').lowercase().replaceFirstChar { it.titlecase() },
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelSmall,
            color = if (finished) Color(0xFF2260A8) else MaterialTheme.colorScheme.primary,
        )
    }
}

@Composable
private fun SyncedCard() {
    AnimatedVisibility(
        visible = true,
        enter = fadeIn() + slideInVertically { it / 3 },
        exit = fadeOut() + slideOutVertically { it / 3 },
    ) {
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            color = Color(0xFFFFF2E2),
        ) {
            Row(modifier = Modifier.padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("You're all set!", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("No pending uploads", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Surface(modifier = Modifier.size(44.dp), shape = CircleShape, color = Color(0xFFFFD29B)) {
                    Box(contentAlignment = Alignment.Center) { Text("✓", color = Color(0xFF159447), fontWeight = FontWeight.Bold) }
                }
            }
        }
    }
}

@Composable
private fun EmptyState(filter: InspectionFilter, hasQuery: Boolean) {
    Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp), color = Color.White) {
        Column(modifier = Modifier.padding(24.dp), horizontalAlignment = Alignment.Start) {
            Text(if (hasQuery) "No matching inspections" else if (filter == InspectionFilter.ACTIVE) "Nothing needs action" else "No inspections here", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(if (hasQuery) "Try another search." else "New assignments will appear here.", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp))
        }
    }
}

@Composable
private fun ErrorState(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp).semantics { liveRegion = LiveRegionMode.Assertive },
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
