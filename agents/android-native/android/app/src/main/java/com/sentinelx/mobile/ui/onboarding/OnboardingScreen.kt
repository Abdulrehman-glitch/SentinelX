package com.sentinelx.mobile.ui.onboarding

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.outlined.Circle
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.sentinelx.mobile.R
import com.sentinelx.mobile.ui.PairingUi
import com.sentinelx.mobile.ui.theme.GlassPanel

// The canonical sequence, in display order; PairingUi.steps holds the subset
// that has actually completed.
private val PAIRING_STEPS = listOf(
    "Server verified",
    "Secure identity created",
    "Device enrolled",
    "Telemetry enabled",
    "Background monitoring scheduled",
)

/**
 * First-run experience: brand welcome → QR pairing (or manual code) →
 * real progress sequence → connected. Console sign-in stays available as an
 * advanced path for operators, never as the default.
 */
@Composable
fun OnboardingScreen(
    pairing: PairingUi,
    initialServerUrl: String,
    onQrScanned: (String) -> Unit,
    onManualPair: (url: String, code: String) -> Unit,
    onRetry: () -> Unit,
    onContinue: () -> Unit,
    onOpenConsoleSignIn: () -> Unit,
) {
    var stage by rememberSaveable { mutableStateOf("welcome") }
    var scanError by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current

    val startScan: () -> Unit = {
        scanError = null
        val options = GmsBarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
            .build()
        GmsBarcodeScanning.getClient(context, options)
            .startScan()
            .addOnSuccessListener { barcode -> barcode.rawValue?.let(onQrScanned) }
            .addOnFailureListener {
                scanError = "QR scanning is unavailable on this device. Enter the pairing code instead."
            }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .imePadding()
            .padding(horizontal = 28.dp, vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Image(
            painter = painterResource(R.drawable.sentinelx_logo),
            contentDescription = null,
            modifier = Modifier
                .size(72.dp)
                .clip(RoundedCornerShape(18.dp)),
        )
        Spacer(Modifier.height(12.dp))
        Text("SentinelX Agent", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(28.dp))

        when {
            pairing.done -> ConnectedPanel(onContinue)
            pairing.inProgress || pairing.steps.isNotEmpty() || pairing.error != null ->
                ProgressPanel(pairing, onRetry = { onRetry(); stage = "connect" })
            stage == "welcome" -> WelcomePanel(onConnect = { stage = "connect" })
            else -> ConnectPanel(
                initialServerUrl = initialServerUrl,
                scanError = scanError,
                onScan = startScan,
                onManualPair = onManualPair,
                onOpenConsoleSignIn = onOpenConsoleSignIn,
            )
        }
    }
}

@Composable
private fun WelcomePanel(onConnect: () -> Unit) {
    Text(
        "Monitor this device with SentinelX.",
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
    Spacer(Modifier.height(32.dp))
    Button(
        onClick = onConnect,
        modifier = Modifier
            .fillMaxWidth()
            .height(54.dp),
    ) {
        Text("Connect to SentinelX")
    }
}

@Composable
private fun ConnectPanel(
    initialServerUrl: String,
    scanError: String?,
    onScan: () -> Unit,
    onManualPair: (url: String, code: String) -> Unit,
    onOpenConsoleSignIn: () -> Unit,
) {
    var showManual by rememberSaveable { mutableStateOf(false) }
    var code by rememberSaveable { mutableStateOf("") }
    var serverUrl by rememberSaveable { mutableStateOf(initialServerUrl) }

    Text("Connect your device", style = MaterialTheme.typography.titleLarge)
    Spacer(Modifier.height(8.dp))
    Text(
        "In SentinelX, open Devices → Add Device → Android, then scan the QR code it shows.",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
    Spacer(Modifier.height(24.dp))

    Button(
        onClick = onScan,
        modifier = Modifier
            .fillMaxWidth()
            .height(54.dp),
    ) {
        Icon(Icons.Filled.QrCodeScanner, contentDescription = null)
        Spacer(Modifier.width(10.dp))
        Text("Scan QR code")
    }

    if (scanError != null) {
        Spacer(Modifier.height(10.dp))
        Text(scanError, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    }

    Spacer(Modifier.height(12.dp))
    TextButton(onClick = { showManual = !showManual }) {
        Text(if (showManual) "Hide manual pairing" else "Enter pairing code instead")
    }

    if (showManual) {
        GlassPanel(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(20.dp)) {
                OutlinedTextField(
                    value = code,
                    onValueChange = { code = it },
                    label = { Text("Pairing code") },
                    placeholder = { Text("sxe_…") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = serverUrl,
                    onValueChange = { serverUrl = it },
                    label = { Text("Server address") },
                    placeholder = { Text("192.168.1.42:8000") },
                    singleLine = true,
                    supportingText = { Text("Shown on the pairing page next to the code.") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(16.dp))
                Button(
                    onClick = { onManualPair(serverUrl, code) },
                    enabled = code.isNotBlank(),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                ) {
                    Text("Connect")
                }
            }
        }
    }

    Spacer(Modifier.height(20.dp))
    HorizontalDivider()
    Spacer(Modifier.height(8.dp))
    TextButton(onClick = onOpenConsoleSignIn) {
        Text("Advanced: console sign-in", color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ProgressPanel(pairing: PairingUi, onRetry: () -> Unit) {
    Text(
        if (pairing.error == null) "Connecting to SentinelX…" else "Pairing failed",
        style = MaterialTheme.typography.titleLarge,
    )
    Spacer(Modifier.height(20.dp))

    GlassPanel(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            val currentIndex = pairing.steps.size
            PAIRING_STEPS.forEachIndexed { index, label ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    when {
                        index < currentIndex -> Icon(
                            Icons.Filled.CheckCircle,
                            contentDescription = "done",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(20.dp),
                        )
                        index == currentIndex && pairing.inProgress -> CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                        )
                        else -> Icon(
                            Icons.Outlined.Circle,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.outlineVariant,
                            modifier = Modifier.size(18.dp),
                        )
                    }
                    Spacer(Modifier.width(12.dp))
                    Text(
                        label,
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (index <= currentIndex) MaterialTheme.colorScheme.onSurface
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }

    if (pairing.error != null) {
        Spacer(Modifier.height(14.dp))
        Text(
            pairing.error,
            color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(14.dp))
        Button(onClick = onRetry, modifier = Modifier.fillMaxWidth().height(50.dp)) {
            Text("Try again")
        }
    }
}

@Composable
private fun ConnectedPanel(onContinue: () -> Unit) {
    Icon(
        Icons.Filled.CheckCircle,
        contentDescription = null,
        tint = MaterialTheme.colorScheme.primary,
        modifier = Modifier.size(56.dp),
    )
    Spacer(Modifier.height(14.dp))
    Text("Device connected", style = MaterialTheme.typography.titleLarge)
    Spacer(Modifier.height(6.dp))
    Text(
        "Telemetry is live. This device now reports to SentinelX.",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
    Spacer(Modifier.height(28.dp))
    Button(onClick = onContinue, modifier = Modifier.fillMaxWidth().height(54.dp)) {
        Text("Continue")
    }
}
