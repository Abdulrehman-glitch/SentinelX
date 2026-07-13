package com.sentinelx.mobile.ui.activity

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sentinelx.mobile.data.db.AgentEvent
import com.sentinelx.mobile.ui.components.SeverityChip
import com.sentinelx.mobile.ui.theme.GlassPanel
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val TIME_FORMAT = DateTimeFormatter.ofPattern("dd MMM HH:mm:ss").withZone(ZoneId.systemDefault())

private val FILTERS = listOf(
    null to "All",
    "monitoring" to "Monitoring",
    "alerts" to "Alerts",
    "connection" to "Connection",
    "system" to "System",
    "user" to "User",
)

@Composable
fun ActivityScreen(
    events: List<AgentEvent>,
    filter: String?,
    onFilterChange: (String?) -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Text(
            "Activity",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(top = 8.dp),
        )
        Text(
            "Chronological timeline of everything this agent did on-device.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(8.dp))

        Row(
            Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            FILTERS.forEach { (id, label) ->
                FilterChip(selected = filter == id, onClick = { onFilterChange(id) }, label = { Text(label) })
            }
        }

        if (events.isEmpty()) {
            Spacer(Modifier.height(16.dp))
            GlassPanel(Modifier.fillMaxWidth()) {
                Text(
                    "No events yet in this category.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(16.dp),
                )
            }
        }

        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(vertical = 12.dp),
        ) {
            items(events, key = { it.id }) { event -> EventRow(event) }
        }
    }
}

@Composable
private fun EventRow(event: AgentEvent) {
    var expanded by rememberSaveable(event.id) { mutableStateOf(false) }
    GlassPanel(Modifier.fillMaxWidth()) {
        Column(
            Modifier
                .clickable { expanded = !expanded }
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Text(
                    TIME_FORMAT.format(Instant.ofEpochMilli(event.atEpochMs)),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.width(110.dp),
                )
                Text(event.title, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                SeverityChip(event.severity)
            }
            if (expanded) {
                Text(
                    buildString {
                        append("Category: ${event.category} · Event #${event.id}")
                        if (event.detail.isNotBlank()) append("\n${event.detail}")
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else if (event.detail.isNotBlank()) {
                Text(
                    event.detail,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
        }
    }
}
