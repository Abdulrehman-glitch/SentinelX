package com.sentinelx.mobile.ui.live

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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sentinelx.mobile.data.db.AgentEvent
import com.sentinelx.mobile.data.prefs.AgentState
import com.sentinelx.mobile.telemetry.TelemetrySnapshot
import com.sentinelx.mobile.ui.components.SeverityChip
import com.sentinelx.mobile.ui.components.StatusDotLabel
import com.sentinelx.mobile.ui.components.relativeTime
import com.sentinelx.mobile.ui.theme.GlassPanel
import com.sentinelx.mobile.ui.theme.SxTone
import kotlinx.coroutines.delay

private data class ModeSpec(val id: String, val label: String, val blurb: String)

private val MODES = listOf(
    ModeSpec("balanced", "Balanced", "Every 60s · battery friendly"),
    ModeSpec("active", "Active", "Every 30s · troubleshooting"),
    ModeSpec("diagnostic", "Diagnostic", "Every 10s · stops after 10 min"),
)

@Composable
fun LiveMonitorScreen(
    state: AgentState,
    snapshot: TelemetrySnapshot?,
    events: List<AgentEvent>,
    onToggleLive: (Boolean) -> Unit,
    onSetMode: (String) -> Unit,
) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            "Live Monitor",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(top = 8.dp),
        )

        ControlCard(state, onToggleLive, onSetMode)

        snapshot?.let { LiveValuesCard(it, state) }

        GlassPanel {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Live event feed", style = MaterialTheme.typography.titleSmall)
                if (events.isEmpty()) {
                    Text(
                        "Monitoring events will appear here.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                events.take(12).forEach { event ->
                    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Text(
                            relativeTime(event.atEpochMs),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.width(64.dp),
                        )
                        Column(Modifier.weight(1f)) {
                            Text(event.title, style = MaterialTheme.typography.bodySmall)
                            if (event.detail.isNotBlank()) {
                                Text(
                                    event.detail,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                        SeverityChip(event.severity)
                    }
                }
            }
        }
        Spacer(Modifier.height(12.dp))
    }
}

@Composable
private fun ControlCard(state: AgentState, onToggleLive: (Boolean) -> Unit, onSetMode: (String) -> Unit) {
    GlassPanel {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    StatusDotLabel(
                        color = if (state.liveModeActive) SxTone.healthy else SxTone.offline,
                        label = if (state.liveModeActive) "Foreground service running" else "Foreground service stopped",
                    )
                    if (state.liveModeActive) {
                        // Ticks once a second so the duration reads live.
                        var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
                        LaunchedEffect(state.liveStartedAtEpochMs) {
                            while (true) {
                                now = System.currentTimeMillis()
                                delay(1_000)
                            }
                        }
                        val elapsed = ((now - state.liveStartedAtEpochMs) / 1000).coerceAtLeast(0)
                        Text(
                            "Running ${elapsed / 60}m ${elapsed % 60}s · sampling every ${state.modeIntervalSeconds}s",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        Text(
                            "Streams telemetry behind a visible notification.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                MODES.forEach { mode ->
                    FilterChip(
                        selected = state.monitoringMode == mode.id,
                        onClick = { onSetMode(mode.id) },
                        label = { Text(mode.label) },
                    )
                }
            }
            Text(
                MODES.first { it.id == state.monitoringMode }.blurb,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Button(
                onClick = { onToggleLive(!state.liveModeActive) },
                enabled = state.isEnrolled,
                colors = if (state.liveModeActive) {
                    ButtonDefaults.buttonColors(containerColor = SxTone.critical)
                } else {
                    ButtonDefaults.buttonColors()
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(
                    if (state.liveModeActive) Icons.Filled.Stop else Icons.Filled.PlayArrow,
                    contentDescription = null,
                )
                Spacer(Modifier.width(6.dp))
                Text(if (state.liveModeActive) "Stop monitoring" else "Start monitoring")
            }
            if (!state.isEnrolled) {
                Text(
                    "Enroll this device from Home before starting Live Mode.",
                    style = MaterialTheme.typography.bodySmall,
                    color = SxTone.warning,
                )
            }
        }
    }
}

@Composable
private fun LiveValuesCard(snapshot: TelemetrySnapshot, state: AgentState) {
    GlassPanel {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Current readings", style = MaterialTheme.typography.titleSmall)
            ValueLine("CPU (estimate)", snapshot.cpuPercent?.let { "%.0f%%".format(it) } ?: "n/a")
            ValueLine("Memory", "%.1f%% used".format(snapshot.memory.usedPercent))
            ValueLine("Storage", "%.1f%% used".format(snapshot.storage.usedPercent))
            ValueLine(
                "Battery",
                "${snapshot.battery.levelPercent}%" +
                    (snapshot.battery.temperatureCelsius?.let { " · %.1f°C".format(it) } ?: "") +
                    if (snapshot.battery.isCharging) " · charging" else "",
            )
            ValueLine("Network", "${snapshot.network.transport}${if (snapshot.network.isMetered) " · metered" else ""}")
            ValueLine("Backend latency", if (state.lastLatencyMs > 0) "${state.lastLatencyMs} ms" else "—")
            ValueLine("Thermal state", snapshot.thermalStatus)
            ValueLine(
                "Backend reachability",
                if (state.lastSyncError.isBlank() && state.lastSyncAtEpochMs > 0) "reachable" else "unreachable",
            )
        }
    }
}

@Composable
private fun ValueLine(label: String, value: String) {
    Row {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(150.dp),
        )
        Text(value, style = MaterialTheme.typography.bodySmall)
    }
}
