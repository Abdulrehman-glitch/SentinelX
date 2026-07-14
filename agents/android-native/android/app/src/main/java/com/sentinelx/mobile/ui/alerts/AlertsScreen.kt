package com.sentinelx.mobile.ui.alerts

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sentinelx.mobile.data.api.dto.AlertDto
import com.sentinelx.mobile.data.prefs.AgentState
import com.sentinelx.mobile.ui.UiFlags
import com.sentinelx.mobile.ui.components.SeverityChip
import com.sentinelx.mobile.ui.theme.GlassPanel
import com.sentinelx.mobile.ui.theme.SxTone
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val TIME_FORMAT = DateTimeFormatter.ofPattern("dd MMM HH:mm").withZone(ZoneId.systemDefault())

/** Human titles + recommended actions per backend alert_type. */
private fun alertPresentation(type: String, message: String): Pair<String, String> = when {
    type == "cpu_high" -> "High CPU load" to "Close heavy apps or let the device cool down."
    type == "memory_high" -> "Memory pressure" to "Close unused apps to free RAM."
    type == "disk_high" -> "Storage nearly full" to "Free device storage or clear app caches."
    // Rule-based alerts carry an opaque "alert_rule:<uuid>" type; the rule
    // name leads the message ("CPU Critical triggered: …"), so title from there.
    type.startsWith("alert_rule:") || type.startsWith("rule:") ->
        (message.substringBefore(" triggered", "").trim().ifBlank { "Alert rule" }) to
            "Review the alert rule on the SentinelX console."
    else -> type.replace('_', ' ').replaceFirstChar { it.uppercase() } to "Review the device on the SentinelX console."
}

@Composable
fun AlertsScreen(
    state: AgentState,
    alerts: List<AlertDto>,
    flags: UiFlags,
    onRefresh: () -> Unit,
    onResolve: (String) -> Unit,
) {
    LaunchedEffect(Unit) { onRefresh() }

    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
            Column(Modifier.weight(1f)) {
                Text("Alerts", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
                Text(
                    "Raised by the backend from this device's telemetry.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = onRefresh, enabled = !flags.alertsRefreshing) {
                Icon(Icons.Filled.Refresh, contentDescription = "Refresh alerts")
            }
        }

        flags.alertsError?.let {
            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }

        if (alerts.isEmpty() && flags.alertsError == null) {
            Spacer(Modifier.height(24.dp))
            GlassPanel(Modifier.fillMaxWidth()) {
                Text(
                    if (flags.alertsRefreshing) "Loading alerts…" else "No alerts for this device. All clear.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(16.dp),
                )
            }
        }

        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(10.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
        ) {
            items(alerts, key = { it.id }) { alert ->
                AlertCard(alert, canResolve = state.canResolveAlerts && state.isLoggedIn, onResolve)
            }
        }
    }
}

@Composable
private fun AlertCard(alert: AlertDto, canResolve: Boolean, onResolve: (String) -> Unit) {
    val (title, recommendation) = alertPresentation(alert.alertType, alert.message)
    GlassPanel(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(title, style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                SeverityChip(alert.severity)
            }
            Text(alert.message, style = MaterialTheme.typography.bodySmall)
            Text(
                "Detected ${TIME_FORMAT.format(Instant.parse(alert.createdAt.ensureZulu()))}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (alert.resolved) {
                Text("Resolved", style = MaterialTheme.typography.labelSmall, color = SxTone.healthy)
            } else {
                Text(
                    "Recommended: $recommendation",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (canResolve) {
                    Row {
                        Spacer(Modifier.weight(1f))
                        TextButton(onClick = { onResolve(alert.id) }) { Text("Mark resolved") }
                    }
                } else {
                    Text(
                        "Viewer role: read-only. Ask an engineer to resolve.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

/** Backend timestamps may arrive without a zone suffix; treat them as UTC. */
private fun String.ensureZulu(): String =
    if (endsWith("Z") || contains('+')) this else this + "Z"
