package com.sentinelx.mobile.ui.health

import android.text.format.Formatter
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sentinelx.mobile.data.prefs.AgentState
import com.sentinelx.mobile.health.HealthBreakdown
import com.sentinelx.mobile.telemetry.TelemetrySnapshot
import com.sentinelx.mobile.ui.components.Sparkline
import com.sentinelx.mobile.ui.components.relativeTime
import com.sentinelx.mobile.ui.theme.GlassPanel
import com.sentinelx.mobile.ui.theme.SxTone

@Composable
fun HealthScreen(
    state: AgentState,
    snapshot: TelemetrySnapshot?,
    history: List<TelemetrySnapshot>,
    health: HealthBreakdown,
    queueDepth: Int,
) {
    val context = LocalContext.current
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            "Health · ${health.overall}",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(top = 8.dp),
        )
        Text(
            "How the score is calculated — five equally weighted categories.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        CategoryCard("Battery health", health.battery, trend = history.map { it.battery.levelPercent.toDouble() }) {
            snapshot?.battery?.let { b ->
                DetailLine("Level", "${b.levelPercent}%")
                DetailLine("Charging", if (b.isCharging) "yes (${b.plugType})" else "no")
                DetailLine("Temperature", b.temperatureCelsius?.let { "%.1f°C".format(it) } ?: "unknown")
                if ((b.temperatureCelsius ?: 0.0) >= 40.0) {
                    Warn("High temperature is reducing this score.")
                }
            }
        }

        CategoryCard("Memory health", health.memory, trend = history.map { it.memory.usedPercent }) {
            snapshot?.memory?.let { m ->
                DetailLine("Total RAM", Formatter.formatShortFileSize(context, m.totalBytes))
                DetailLine("Available", Formatter.formatShortFileSize(context, m.availableBytes))
                DetailLine("Used", "%.1f%%".format(m.usedPercent))
                if (m.lowMemory) Warn("Android reports a low-memory condition.")
            }
        }

        CategoryCard("Storage health", health.storage, trend = history.map { it.storage.usedPercent }) {
            snapshot?.storage?.let { s ->
                DetailLine("Total", Formatter.formatShortFileSize(context, s.totalBytes))
                DetailLine("Free", Formatter.formatShortFileSize(context, s.availableBytes))
                DetailLine("Used", "%.1f%%".format(s.usedPercent))
                DetailLine("Pending upload", "$queueDepth queued sample(s)")
            }
        }

        CategoryCard("Network health", health.network, trend = history.map { if (it.network.isConnected) 100.0 else 0.0 }) {
            snapshot?.network?.let { n ->
                DetailLine("Connection", n.transport)
                DetailLine("Metered", if (n.isMetered) "yes" else "no")
                DetailLine("Validated", if (n.isValidated) "yes" else "no")
                DetailLine("Backend latency", if (state.lastLatencyMs > 0) "${state.lastLatencyMs} ms" else "—")
                DetailLine("Last successful upload", relativeTime(state.lastSyncAtEpochMs))
                DetailLine("Consecutive failures", state.consecutiveSyncFailures.toString())
            }
        }

        CategoryCard("Agent reliability", health.agent, trend = null) {
            DetailLine("Last upload", relativeTime(state.lastSyncAtEpochMs))
            DetailLine("Queue", "$queueDepth sample(s) pending")
            DetailLine("Token state", if (state.isEnrolled) "device credential present" else "not enrolled")
            DetailLine("Monitoring mode", state.monitoringMode)
            snapshot?.let { DetailLine("Thermal state", it.thermalStatus) }
            if (state.lastSyncError.isNotBlank()) Warn(state.lastSyncError)
        }
        Spacer(Modifier.height(12.dp))
    }
}

@Composable
private fun CategoryCard(title: String, score: Int, trend: List<Double>?, content: @Composable () -> Unit) {
    GlassPanel {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row {
                Text(title, style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                Text(
                    "$score",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = scoreColor(score),
                )
            }
            LinearProgressIndicator(
                progress = { score / 100f },
                color = scoreColor(score),
                trackColor = MaterialTheme.colorScheme.surfaceVariant,
                modifier = Modifier.fillMaxWidth(),
            )
            content()
            trend?.let { if (it.size >= 2) Sparkline(it, scoreColor(score)) }
        }
    }
}

@Composable
private fun scoreColor(score: Int) = when {
    score >= 85 -> SxTone.healthy
    score >= 60 -> SxTone.warning
    else -> SxTone.critical
}

@Composable
private fun DetailLine(label: String, value: String) {
    Row {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(160.dp),
        )
        Text(value, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun Warn(text: String) {
    Text(text, style = MaterialTheme.typography.bodySmall, color = SxTone.warning)
}
