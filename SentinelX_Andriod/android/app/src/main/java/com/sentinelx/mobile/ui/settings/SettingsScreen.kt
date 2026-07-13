package com.sentinelx.mobile.ui.settings

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
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sentinelx.mobile.BuildConfig
import com.sentinelx.mobile.data.prefs.AgentState
import com.sentinelx.mobile.ui.UiFlags
import com.sentinelx.mobile.ui.theme.GlassPanel
import com.sentinelx.mobile.ui.theme.SxTone

@Composable
fun SettingsScreen(
    state: AgentState,
    flags: UiFlags,
    onSetMonitoringMode: (String) -> Unit,
    onSetThemeMode: (String) -> Unit,
    onSetWifiOnly: (Boolean) -> Unit,
    onSetPauseOnLowBattery: (Boolean) -> Unit,
    onSetReducedMotion: (Boolean) -> Unit,
    onTestConnection: () -> Unit,
    onDeleteLocalData: () -> Unit,
    onUnenroll: () -> Unit,
    onLogout: () -> Unit,
) {
    var confirmUnenroll by rememberSaveable { mutableStateOf(false) }
    var confirmDeleteData by rememberSaveable { mutableStateOf(false) }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            "Settings",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(top = 8.dp),
        )

        Section("Account & enrollment") {
            InfoLine("Signed in as", state.userEmail.ifBlank { "not signed in" })
            InfoLine("Role", state.userRole.ifBlank { "—" })
            InfoLine("Organisation", state.orgName.ifBlank { "—" })
            InfoLine("Device", state.deviceHostname.ifBlank { "not enrolled" })
            InfoLine("Agent ID", state.deviceId.ifBlank { "—" })
            InfoLine("Server", state.baseUrl.ifBlank { "—" })
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.isEnrolled) {
                    OutlinedButton(onClick = { confirmUnenroll = true }, modifier = Modifier.weight(1f)) {
                        Text("Unenroll device", color = SxTone.critical)
                    }
                }
                if (state.isLoggedIn) {
                    OutlinedButton(onClick = onLogout, modifier = Modifier.weight(1f)) {
                        Text("Sign out")
                    }
                }
            }
        }

        Section("Monitoring") {
            Text(
                "Live Mode cadence — Balanced 60s, Active 30s, Diagnostic 10s (auto-stops after 10 min).",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("balanced" to "Balanced", "active" to "Active", "diagnostic" to "Diagnostic").forEach { (id, label) ->
                    FilterChip(selected = state.monitoringMode == id, onClick = { onSetMonitoringMode(id) }, label = { Text(label) })
                }
            }
            ToggleRow(
                "Wi-Fi-only uploads",
                "Queue telemetry until Wi-Fi is available",
                state.wifiOnlyUploads,
                onSetWifiOnly,
            )
            ToggleRow(
                "Pause on low battery",
                "Skip uploads below 15% unless charging",
                state.pauseOnLowBattery,
                onSetPauseOnLowBattery,
            )
        }

        Section("Appearance") {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("light" to "Light", "dark" to "Dark", "system" to "System").forEach { (id, label) ->
                    FilterChip(selected = state.themeMode == id, onClick = { onSetThemeMode(id) }, label = { Text(label) })
                }
            }
            ToggleRow(
                "Reduced motion",
                "Disable decorative animations like the health orb sweep",
                state.reducedMotion,
                onSetReducedMotion,
            )
        }

        Section("Privacy & data") {
            Text(
                "SentinelX collects device telemetry only: CPU estimate, memory, storage, " +
                    "battery, network transport, and thermal state. No contacts, no location, " +
                    "no content. Data goes to your organisation's SentinelX backend.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedButton(onClick = { confirmDeleteData = true }, modifier = Modifier.fillMaxWidth()) {
                Text("Delete local data", color = SxTone.critical)
            }
        }

        Section("Diagnostics & about") {
            OutlinedButton(onClick = onTestConnection, enabled = !flags.connectionTestInProgress, modifier = Modifier.fillMaxWidth()) {
                Text(if (flags.connectionTestInProgress) "Testing…" else "Test server connection")
            }
            flags.connectionTestResult?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            InfoLine("Agent version", BuildConfig.VERSION_NAME)
            InfoLine("Live interval", "${state.modeIntervalSeconds}s (${state.monitoringMode})")
            InfoLine("Background sync", "every 15 minutes (WorkManager)")
        }
        Spacer(Modifier.height(12.dp))
    }

    if (confirmUnenroll) {
        AlertDialog(
            onDismissRequest = { confirmUnenroll = false },
            title = { Text("Unenroll this device?") },
            text = { Text("The device credential is removed and telemetry stops. Queued samples are deleted.") },
            confirmButton = {
                TextButton(onClick = { confirmUnenroll = false; onUnenroll() }) { Text("Unenroll", color = SxTone.critical) }
            },
            dismissButton = { TextButton(onClick = { confirmUnenroll = false }) { Text("Cancel") } },
        )
    }
    if (confirmDeleteData) {
        AlertDialog(
            onDismissRequest = { confirmDeleteData = false },
            title = { Text("Delete local data?") },
            text = { Text("Clears the offline telemetry queue and the on-device activity timeline. Data already uploaded is unaffected.") },
            confirmButton = {
                TextButton(onClick = { confirmDeleteData = false; onDeleteLocalData() }) { Text("Delete", color = SxTone.critical) }
            },
            dismissButton = { TextButton(onClick = { confirmDeleteData = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun Section(title: String, content: @Composable () -> Unit) {
    GlassPanel(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall)
            content()
        }
    }
}

@Composable
private fun InfoLine(label: String, value: String) {
    Row {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(140.dp),
        )
        Text(value, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun ToggleRow(title: String, subtitle: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.toggleable(value = checked, role = Role.Switch, onValueChange = onChange),
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyMedium)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = null)
    }
}
