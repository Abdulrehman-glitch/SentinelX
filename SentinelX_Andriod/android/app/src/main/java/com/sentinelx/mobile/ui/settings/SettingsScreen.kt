package com.sentinelx.mobile.ui.settings

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.sentinelx.mobile.BuildConfig
import androidx.compose.ui.graphics.Color
import com.sentinelx.mobile.data.prefs.AgentState
import com.sentinelx.mobile.ui.UiFlags
import com.sentinelx.mobile.ui.theme.GlassPanel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    state: AgentState,
    flags: UiFlags,
    onSetInterval: (Int) -> Unit,
    onTestConnection: () -> Unit,
    onUnenroll: () -> Unit,
    onLogout: () -> Unit,
    onBack: () -> Unit,
) {
    var confirmUnenroll by remember { mutableStateOf(false) }
    var confirmLogout by remember { mutableStateOf(false) }

    // System back should pop to the dashboard, not exit the app.
    BackHandler(onBack = onBack)

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
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
            SettingsCard("Account") {
                InfoRow("Signed in as", state.userEmail.ifBlank { "—" })
                InfoRow("Role", state.userRole.ifBlank { "—" })
                InfoRow("Organization", state.orgName.ifBlank { "—" })
                InfoRow("Server", state.baseUrl.ifBlank { "—" })
            }

            SettingsCard("Device") {
                InfoRow("Hostname", state.deviceHostname.ifBlank { "not enrolled" })
                InfoRow("Device ID", state.deviceId.take(13).ifBlank { "—" })
                InfoRow("Agent version", BuildConfig.VERSION_NAME)
            }

            SettingsCard("Live Mode interval") {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(15, 30, 60).forEach { seconds ->
                        FilterChip(
                            selected = state.liveIntervalSeconds == seconds,
                            onClick = { onSetInterval(seconds) },
                            label = { Text("${seconds}s") },
                        )
                    }
                }
                Text(
                    "Background sync also runs every 15 minutes via WorkManager, regardless of Live Mode.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            SettingsCard("Diagnostics") {
                OutlinedButton(
                    onClick = onTestConnection,
                    enabled = !flags.connectionTestInProgress && state.baseUrl.isNotBlank(),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (flags.connectionTestInProgress) "Testing…" else "Test server connection") }
                flags.connectionTestResult?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            SettingsCard("Danger zone") {
                OutlinedButton(
                    onClick = { confirmUnenroll = true },
                    enabled = state.isEnrolled,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Unlink device") }
                OutlinedButton(
                    onClick = { confirmLogout = true },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Sign out") }
                Text(
                    "Unlinking clears the local device token and telemetry queue. Signing out keeps the agent enrolled.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(16.dp))
        }
    }

    if (confirmUnenroll) {
        AlertDialog(
            onDismissRequest = { confirmUnenroll = false },
            title = { Text("Unlink device?") },
            text = { Text("This stops telemetry and deletes the local device token and queued samples. You can enroll again later.") },
            confirmButton = {
                TextButton(onClick = { confirmUnenroll = false; onUnenroll() }) { Text("Unlink") }
            },
            dismissButton = {
                TextButton(onClick = { confirmUnenroll = false }) { Text("Cancel") }
            },
        )
    }

    if (confirmLogout) {
        AlertDialog(
            onDismissRequest = { confirmLogout = false },
            title = { Text("Sign out?") },
            text = { Text("The enrolled agent keeps syncing on its device token. Sign in again to manage it.") },
            confirmButton = {
                TextButton(onClick = { confirmLogout = false; onLogout() }) { Text("Sign out") }
            },
            dismissButton = {
                TextButton(onClick = { confirmLogout = false }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun SettingsCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    GlassPanel {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall)
            content()
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.fillMaxWidth(0.4f),
        )
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
