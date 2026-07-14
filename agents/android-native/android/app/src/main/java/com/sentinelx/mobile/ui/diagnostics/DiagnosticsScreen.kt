package com.sentinelx.mobile.ui.diagnostics

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Error
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sentinelx.mobile.BuildConfig
import com.sentinelx.mobile.diagnostics.DiagnosticResult
import com.sentinelx.mobile.diagnostics.DiagnosticVerdict
import com.sentinelx.mobile.diagnostics.DiagnosticsRunner
import com.sentinelx.mobile.ui.UiFlags
import com.sentinelx.mobile.ui.theme.GlassPanel
import com.sentinelx.mobile.ui.theme.SxTone

@Composable
fun DiagnosticsScreen(
    results: List<DiagnosticResult>,
    flags: UiFlags,
    onRunAll: () -> Unit,
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
            "Diagnostics",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(top = 8.dp),
        )
        Text(
            "Twelve one-tap checks across network, backend, and this agent.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Button(onClick = onRunAll, enabled = !flags.diagnosticsRunning, modifier = Modifier.fillMaxWidth()) {
            if (flags.diagnosticsRunning) {
                CircularProgressIndicator(Modifier.size(18.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                Spacer(Modifier.width(8.dp))
                Text("Running ${results.size}/12…")
            } else {
                Text(if (results.isEmpty()) "Run all tests" else "Run again")
            }
        }

        if (results.isNotEmpty()) {
            GlassPanel(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(DiagnosticsRunner.summaryLine(results), style = MaterialTheme.typography.titleSmall)
                    Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        Count("Passed", results.count { it.verdict == DiagnosticVerdict.PASS }, SxTone.healthy)
                        Count("Warnings", results.count { it.verdict == DiagnosticVerdict.WARN }, SxTone.warning)
                        Count("Failed", results.count { it.verdict == DiagnosticVerdict.FAIL }, SxTone.critical)
                    }
                }
            }

            GlassPanel(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    results.forEach { r -> ResultRow(r) }
                }
            }

            if (!flags.diagnosticsRunning) {
                OutlinedButton(
                    onClick = {
                        val report = DiagnosticsRunner.redactedReport(results, BuildConfig.VERSION_NAME)
                        val send = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_SUBJECT, "SentinelX diagnostic report")
                            putExtra(Intent.EXTRA_TEXT, report)
                        }
                        context.startActivity(Intent.createChooser(send, "Share diagnostic report"))
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Share redacted report")
                }
            }
        }
        Spacer(Modifier.height(12.dp))
    }
}

@Composable
private fun Count(label: String, value: Int, color: androidx.compose.ui.graphics.Color) {
    Text("$value $label", style = MaterialTheme.typography.bodySmall, color = color, fontWeight = FontWeight.SemiBold)
}

@Composable
private fun ResultRow(result: DiagnosticResult) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        val (icon, tint) = when (result.verdict) {
            DiagnosticVerdict.PASS -> Icons.Filled.CheckCircle to SxTone.healthy
            DiagnosticVerdict.WARN -> Icons.Filled.Error to SxTone.warning
            DiagnosticVerdict.FAIL -> Icons.Filled.Cancel to SxTone.critical
        }
        Icon(icon, contentDescription = result.verdict.name, tint = tint, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(result.name, style = MaterialTheme.typography.bodyMedium)
            Text(
                result.detail,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            "${result.durationMs} ms",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
