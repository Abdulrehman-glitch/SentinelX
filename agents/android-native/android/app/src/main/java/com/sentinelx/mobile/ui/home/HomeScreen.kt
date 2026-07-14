package com.sentinelx.mobile.ui.home

import android.os.Build
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.material.icons.filled.BatteryChargingFull
import androidx.compose.material.icons.filled.BatteryStd
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.CloudUpload
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.MonitorHeart
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sentinelx.mobile.data.prefs.AgentState
import com.sentinelx.mobile.health.HealthBreakdown
import com.sentinelx.mobile.health.HealthStatus
import com.sentinelx.mobile.telemetry.TelemetrySnapshot
import com.sentinelx.mobile.ui.UiFlags
import com.sentinelx.mobile.ui.components.HealthOrb
import com.sentinelx.mobile.ui.components.Sparkline
import com.sentinelx.mobile.ui.components.StatusDotLabel
import com.sentinelx.mobile.ui.components.healthColor
import com.sentinelx.mobile.ui.components.relativeTime
import com.sentinelx.mobile.ui.theme.GlassPanel
import com.sentinelx.mobile.ui.theme.SxTone

@Composable
fun HomeScreen(
    state: AgentState,
    snapshot: TelemetrySnapshot?,
    history: List<TelemetrySnapshot>,
    health: HealthBreakdown,
    queueDepth: Int,
    unresolvedAlerts: Int,
    flags: UiFlags,
    onEnroll: () -> Unit,
    onCollectNow: () -> Unit,
    onUploadNow: () -> Unit,
    onOpenLive: () -> Unit,
    onOpenHealth: () -> Unit,
    onOpenDiagnostics: () -> Unit,
) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Header(state, health)

        if (!state.isEnrolled) {
            EnrollCard(state, flags, onEnroll)
        }

        // Health orb is the visual anchor; tapping opens the score breakdown.
        Box(
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onOpenHealth),
            contentAlignment = Alignment.Center,
        ) {
            val status = if (snapshot?.network?.isConnected == false) HealthStatus.OFFLINE else health.status
            HealthOrb(score = health.overall, status = status, animate = !state.reducedMotion)
        }

        snapshot?.let { MetricGrid(it, history, onOpenHealth) }

        QuickActions(state, flags, onCollectNow, onUploadNow, onOpenLive, onOpenDiagnostics)

        AgentStatusStrip(state, queueDepth, unresolvedAlerts)

        flags.manualSyncResult?.let {
            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(12.dp))
    }
}

@Composable
private fun Header(state: AgentState, health: HealthBreakdown) {
    Column(Modifier.padding(top = 8.dp)) {
        Text(
            state.deviceHostname.ifBlank { Build.MODEL },
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            "${Build.MANUFACTURER} ${Build.MODEL} · Protected by SentinelX",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(6.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            val connected = state.lastSyncError.isBlank() && state.lastSyncAtEpochMs > 0
            StatusDotLabel(
                color = when {
                    state.lastSyncError.isNotBlank() -> SxTone.critical
                    connected -> SxTone.healthy
                    else -> SxTone.warning
                },
                label = if (connected) "Connected · last sync ${relativeTime(state.lastSyncAtEpochMs)}"
                else if (state.lastSyncError.isNotBlank()) "Backend unreachable"
                else "Waiting for first sync",
            )
            StatusDotLabel(
                color = if (state.liveModeActive) SxTone.accent else SxTone.offline,
                label = if (state.liveModeActive) "Live · ${state.monitoringMode}" else "Mode: ${state.monitoringMode}",
            )
        }
    }
}

@Composable
private fun EnrollCard(state: AgentState, flags: UiFlags, onEnroll: () -> Unit) {
    GlassPanel {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Enroll this device", style = MaterialTheme.typography.titleMedium)
            Text(
                "Register this phone as a managed SentinelX device and start sending telemetry.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (!state.canEnroll) {
                Text(
                    "Signed in as ${state.userEmail} (${state.userRole}). Enrollment needs an admin, owner, or platform_admin account.",
                    style = MaterialTheme.typography.bodySmall,
                    color = SxTone.warning,
                )
            }
            flags.enrollError?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
            Button(onClick = onEnroll, enabled = state.canEnroll && !flags.enrollInProgress, modifier = Modifier.fillMaxWidth()) {
                if (flags.enrollInProgress) {
                    CircularProgressIndicator(Modifier.height(20.dp).width(20.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                } else {
                    Text("Enroll device")
                }
            }
        }
    }
}

@Composable
private fun MetricGrid(snapshot: TelemetrySnapshot, history: List<TelemetrySnapshot>, onOpen: () -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        MetricTile(
            icon = if (snapshot.battery.isCharging) Icons.Filled.BatteryChargingFull else Icons.Filled.BatteryStd,
            title = "Battery",
            value = "${snapshot.battery.levelPercent}%",
            label = if (snapshot.battery.isCharging) "Charging" else "Discharging",
            trend = history.map { it.battery.levelPercent.toDouble() },
            tone = if (snapshot.battery.levelPercent < 20) SxTone.critical else SxTone.healthy,
            onClick = onOpen,
            modifier = Modifier.weight(1f),
        )
        MetricTile(
            icon = Icons.Filled.Memory,
            title = "Memory",
            value = "%.0f%%".format(snapshot.memory.usedPercent),
            label = if (snapshot.memory.lowMemory) "Low memory" else "In use",
            trend = history.map { it.memory.usedPercent },
            tone = if (snapshot.memory.usedPercent > 85) SxTone.critical else SxTone.accent,
            onClick = onOpen,
            modifier = Modifier.weight(1f),
        )
    }
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        MetricTile(
            icon = Icons.Filled.Storage,
            title = "Storage",
            value = "%.0f%%".format(snapshot.storage.usedPercent),
            label = "Used",
            trend = history.map { it.storage.usedPercent },
            tone = if (snapshot.storage.usedPercent > 85) SxTone.critical else SxTone.accent,
            onClick = onOpen,
            modifier = Modifier.weight(1f),
        )
        MetricTile(
            icon = Icons.Filled.Wifi,
            title = "Network",
            value = snapshot.network.transport.replaceFirstChar { it.uppercase() },
            label = if (snapshot.network.isConnected) "Connected" else "Offline",
            trend = history.map { if (it.network.isConnected) 100.0 else 0.0 },
            tone = if (snapshot.network.isConnected) SxTone.healthy else SxTone.critical,
            onClick = onOpen,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun MetricTile(
    icon: ImageVector,
    title: String,
    value: String,
    label: String,
    trend: List<Double>,
    tone: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    GlassPanel(modifier) {
        Column(
            Modifier
                .clickable(onClick = onClick)
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, contentDescription = null, tint = tone)
                Spacer(Modifier.width(8.dp))
                Text(title, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
            Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Sparkline(trend, tone)
        }
    }
}

@Composable
private fun QuickActions(
    state: AgentState,
    flags: UiFlags,
    onCollectNow: () -> Unit,
    onUploadNow: () -> Unit,
    onOpenLive: () -> Unit,
    onOpenDiagnostics: () -> Unit,
) {
    GlassPanel {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Quick actions", style = MaterialTheme.typography.titleSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onCollectNow, enabled = state.isEnrolled, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Filled.Bolt, contentDescription = null, Modifier.height(18.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Collect")
                }
                OutlinedButton(onClick = onUploadNow, enabled = state.isEnrolled && !flags.manualSyncInProgress, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Filled.CloudUpload, contentDescription = null, Modifier.height(18.dp))
                    Spacer(Modifier.width(4.dp))
                    Text(if (flags.manualSyncInProgress) "…" else "Upload")
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onOpenLive, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Filled.MonitorHeart, contentDescription = null, Modifier.height(18.dp))
                    Spacer(Modifier.width(4.dp))
                    Text(if (state.liveModeActive) "Live view" else "Go live")
                }
                OutlinedButton(onClick = onOpenDiagnostics, modifier = Modifier.weight(1f)) {
                    Text("Diagnostics")
                }
            }
        }
    }
}

@Composable
private fun AgentStatusStrip(state: AgentState, queueDepth: Int, unresolvedAlerts: Int) {
    GlassPanel {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Agent status", style = MaterialTheme.typography.titleSmall)
            StatusLine("Active alerts", if (unresolvedAlerts > 0) "$unresolvedAlerts open" else "none",
                if (unresolvedAlerts > 0) SxTone.warning else MaterialTheme.colorScheme.onSurface)
            StatusLine("Pending telemetry", "$queueDepth sample(s)")
            StatusLine("Last upload", relativeTime(state.lastSyncAtEpochMs))
            StatusLine("Backend latency", if (state.lastLatencyMs > 0) "${state.lastLatencyMs} ms" else "—")
            StatusLine("Monitoring interval", "${state.modeIntervalSeconds}s (${state.monitoringMode})")
            if (state.lastSyncError.isNotBlank()) {
                Text(state.lastSyncError, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
private fun StatusLine(label: String, value: String, valueColor: Color = Color.Unspecified) {
    Row {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(150.dp),
        )
        Text(value, style = MaterialTheme.typography.bodySmall, color = if (valueColor == Color.Unspecified) MaterialTheme.colorScheme.onSurface else valueColor)
    }
}
