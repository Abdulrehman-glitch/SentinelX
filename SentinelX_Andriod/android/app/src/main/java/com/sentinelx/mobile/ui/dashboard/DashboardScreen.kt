package com.sentinelx.mobile.ui.dashboard

import android.text.format.Formatter
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BatteryChargingFull
import androidx.compose.material.icons.filled.BatteryStd
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sentinelx.mobile.data.prefs.AgentState
import com.sentinelx.mobile.telemetry.TelemetrySnapshot
import com.sentinelx.mobile.ui.UiFlags
import com.sentinelx.mobile.ui.theme.GlassPanel
import com.sentinelx.mobile.ui.theme.SxAmber
import com.sentinelx.mobile.ui.theme.SxGreen
import com.sentinelx.mobile.ui.theme.SxRed
import java.text.DateFormat
import java.util.Date

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    state: AgentState,
    snapshot: TelemetrySnapshot?,
    queueDepth: Int,
    flags: UiFlags,
    onEnroll: () -> Unit,
    onSyncNow: () -> Unit,
    onToggleLive: (Boolean) -> Unit,
    onOpenSettings: () -> Unit,
) {
    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("SentinelX Agent", fontWeight = FontWeight.SemiBold)
                        Text(
                            state.orgName.ifBlank { "No organization" },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Filled.Settings, contentDescription = "Settings")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (!state.isEnrolled) {
                EnrollCard(state, flags, onEnroll)
            } else {
                AgentStatusCard(state, queueDepth, flags, onSyncNow, onToggleLive)
            }

            snapshot?.let { TelemetryCards(it) }
            Spacer(Modifier.height(16.dp))
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
                    color = SxAmber,
                )
            }
            flags.enrollError?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
            Button(
                onClick = onEnroll,
                enabled = state.canEnroll && !flags.enrollInProgress,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (flags.enrollInProgress) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = MaterialTheme.colorScheme.onPrimary,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Text("Enroll device")
                }
            }
        }
    }
}

@Composable
private fun AgentStatusCard(
    state: AgentState,
    queueDepth: Int,
    flags: UiFlags,
    onSyncNow: () -> Unit,
    onToggleLive: (Boolean) -> Unit,
) {
    GlassPanel {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                // Amber until the first successful sync — green would claim health we haven't proven.
                val dotColor = when {
                    state.lastSyncError.isNotBlank() -> SxRed
                    state.lastSyncAtEpochMs > 0 -> SxGreen
                    else -> SxAmber
                }
                Box(
                    Modifier
                        .size(10.dp)
                        .background(dotColor, CircleShape)
                )
                Spacer(Modifier.width(8.dp))
                Text(state.deviceHostname, style = MaterialTheme.typography.titleMedium)
            }

            StatusRow("Server", state.baseUrl)
            StatusRow(
                "Last sync",
                if (state.lastSyncAtEpochMs > 0)
                    DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.MEDIUM)
                        .format(Date(state.lastSyncAtEpochMs))
                else "never",
            )
            StatusRow("Queued samples", queueDepth.toString())
            if (state.lastSyncError.isNotBlank()) {
                Text(
                    state.lastSyncError,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
            flags.manualSyncResult?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }

            Row(
                verticalAlignment = Alignment.CenterVertically,
                // Whole row is the toggle so screen readers announce "Live Mode" with the switch.
                modifier = Modifier.toggleable(
                    value = state.liveModeActive,
                    role = Role.Switch,
                    onValueChange = onToggleLive,
                ),
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Live Mode", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "Stream every ${state.liveIntervalSeconds}s with a visible notification",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(checked = state.liveModeActive, onCheckedChange = null)
            }

            OutlinedButton(
                onClick = onSyncNow,
                enabled = !flags.manualSyncInProgress,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (flags.manualSyncInProgress) "Syncing…" else "Sync now")
            }
        }
    }
}

@Composable
private fun StatusRow(label: String, value: String) {
    Row {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(120.dp),
        )
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun TelemetryCards(snapshot: TelemetrySnapshot) {
    val context = LocalContext.current

    Text(
        "Device telemetry",
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )

    MetricCard(
        icon = if (snapshot.battery.isCharging) Icons.Filled.BatteryChargingFull else Icons.Filled.BatteryStd,
        title = "Battery",
        value = "${snapshot.battery.levelPercent}%",
        detail = buildString {
            append(if (snapshot.battery.isCharging) "Charging (${snapshot.battery.plugType})" else "Discharging")
            snapshot.battery.temperatureCelsius?.let { append(" · %.1f°C".format(it)) }
        },
        fraction = snapshot.battery.levelPercent / 100f,
        barColor = if (snapshot.battery.levelPercent < 20) SxRed else SxGreen,
    )

    MetricCard(
        icon = Icons.Filled.Memory,
        title = "Memory",
        value = "%.1f%%".format(snapshot.memory.usedPercent),
        detail = "${Formatter.formatShortFileSize(context, snapshot.memory.availableBytes)} free of " +
            Formatter.formatShortFileSize(context, snapshot.memory.totalBytes),
        fraction = (snapshot.memory.usedPercent / 100).toFloat(),
        barColor = if (snapshot.memory.usedPercent > 85) SxRed else MaterialTheme.colorScheme.primary,
    )

    MetricCard(
        icon = Icons.Filled.Storage,
        title = "Storage",
        value = "%.1f%%".format(snapshot.storage.usedPercent),
        detail = "${Formatter.formatShortFileSize(context, snapshot.storage.availableBytes)} free of " +
            Formatter.formatShortFileSize(context, snapshot.storage.totalBytes),
        fraction = (snapshot.storage.usedPercent / 100).toFloat(),
        barColor = if (snapshot.storage.usedPercent > 85) SxRed else MaterialTheme.colorScheme.primary,
    )

    MetricCard(
        icon = Icons.Filled.Speed,
        title = "CPU (estimate)",
        value = snapshot.cpuPercent?.let { "%.0f%%".format(it) } ?: "n/a",
        detail = if (snapshot.cpuPercent != null) "From per-core frequency scaling" else "Not readable on this device",
        fraction = ((snapshot.cpuPercent ?: 0.0) / 100).toFloat(),
        barColor = MaterialTheme.colorScheme.primary,
    )

    MetricCard(
        icon = Icons.Filled.Wifi,
        title = "Network",
        value = snapshot.network.transport.replaceFirstChar { it.uppercase() },
        detail = buildString {
            append(if (snapshot.network.isConnected) "Connected" else "Disconnected")
            if (snapshot.network.isMetered) append(" · metered")
            if (snapshot.network.isValidated) append(" · validated")
        },
        fraction = if (snapshot.network.isConnected) 1f else 0f,
        barColor = if (snapshot.network.isConnected) SxGreen else SxRed,
    )
}

@Composable
private fun MetricCard(
    icon: ImageVector,
    title: String,
    value: String,
    detail: String,
    fraction: Float,
    barColor: Color,
) {
    GlassPanel {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(10.dp))
                Text(title, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
                Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
            LinearProgressIndicator(
                progress = { fraction.coerceIn(0f, 1f) },
                color = barColor,
                trackColor = MaterialTheme.colorScheme.surfaceVariant,
                modifier = Modifier.fillMaxWidth(),
            )
            Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
