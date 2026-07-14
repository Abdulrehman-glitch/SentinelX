package com.sentinelx.mobile.diagnostics

import android.content.Context
import android.os.Build
import android.os.PowerManager
import androidx.core.app.NotificationManagerCompat
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.sentinelx.mobile.core.AppContainer
import com.sentinelx.mobile.data.api.ApiClient
import com.sentinelx.mobile.data.api.HostSelectionInterceptor
import com.sentinelx.mobile.data.db.QueuedMetric
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import retrofit2.HttpException
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.URL
import java.time.Instant
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import kotlin.math.abs

enum class DiagnosticVerdict { PASS, WARN, FAIL }

data class DiagnosticResult(
    val name: String,
    val verdict: DiagnosticVerdict,
    val detail: String,
    val durationMs: Long,
)

/**
 * One-tap diagnostic suite. Every test is local and side-effect free except
 * the telemetry upload test, which sends one real sample. The shareable
 * summary never includes tokens, passwords, or account identifiers.
 */
class DiagnosticsRunner(
    private val context: Context,
    private val container: AppContainer,
) {

    suspend fun runAll(onResult: suspend (DiagnosticResult) -> Unit): List<DiagnosticResult> {
        val results = mutableListOf<DiagnosticResult>()
        suspend fun run(name: String, block: suspend () -> Pair<DiagnosticVerdict, String>) {
            val startedAt = System.currentTimeMillis()
            val (verdict, detail) = try {
                block()
            } catch (t: Throwable) {
                DiagnosticVerdict.FAIL to ApiClient.readableError(t)
            }
            val result = DiagnosticResult(name, verdict, detail, System.currentTimeMillis() - startedAt)
            results += result
            onResult(result)
        }

        run("Internet connection") { internetTest() }
        run("DNS resolution") { dnsTest() }
        run("Transport security") { tlsTest() }
        run("Backend API") { backendTest() }
        run("Authentication token") { authTest() }
        run("Telemetry upload") { uploadTest() }
        run("Local database") { databaseTest() }
        run("Background worker") { workerTest() }
        run("Notifications") { notificationTest() }
        run("Battery optimisation") { batteryOptimisationTest() }
        run("Storage headroom") { storageTest() }
        run("Clock skew") { clockSkewTest() }

        container.eventLogger.log(
            "system", "info", "Diagnostics completed",
            summaryLine(results),
        )
        return results
    }

    private fun internetTest(): Pair<DiagnosticVerdict, String> {
        val net = container.collector.collectNetwork()
        return when {
            net.isConnected && net.isValidated -> DiagnosticVerdict.PASS to "Connected via ${net.transport}, validated by Android"
            net.isConnected -> DiagnosticVerdict.WARN to "Connected via ${net.transport} but not validated (captive portal?)"
            else -> DiagnosticVerdict.FAIL to "No network connection"
        }
    }

    private suspend fun dnsTest(): Pair<DiagnosticVerdict, String> = withContext(Dispatchers.IO) {
        val host = serverHost() ?: return@withContext DiagnosticVerdict.FAIL to "No server URL configured"
        val address = InetAddress.getByName(host)
        DiagnosticVerdict.PASS to "$host resolves to ${address.hostAddress}"
    }

    private suspend fun tlsTest(): Pair<DiagnosticVerdict, String> = withContext(Dispatchers.IO) {
        val base = normalizedBase() ?: return@withContext DiagnosticVerdict.FAIL to "No server URL configured"
        if (base.startsWith("https://")) {
            val connection = URL("$base/api/v1/health").openConnection() as HttpURLConnection
            connection.connectTimeout = 8000
            connection.connect()
            val secure = connection is javax.net.ssl.HttpsURLConnection
            connection.disconnect()
            if (secure) DiagnosticVerdict.PASS to "TLS handshake succeeded"
            else DiagnosticVerdict.WARN to "Connection established but not TLS"
        } else {
            DiagnosticVerdict.WARN to "Cleartext HTTP (development transport) — use HTTPS in production"
        }
    }

    private suspend fun backendTest(): Pair<DiagnosticVerdict, String> {
        val startedAt = System.currentTimeMillis()
        val health = container.api.health()
        val latency = System.currentTimeMillis() - startedAt
        val healthy = health.apiStatus == "online" && health.databaseStatus == "online"
        val detail = "API ${health.apiStatus}, database ${health.databaseStatus} · ${latency} ms"
        return (if (healthy) DiagnosticVerdict.PASS else DiagnosticVerdict.FAIL) to detail
    }

    private suspend fun authTest(): Pair<DiagnosticVerdict, String> {
        val token = container.secureStore.deviceToken
            ?: return DiagnosticVerdict.WARN to "No device token — device not enrolled yet"
        return try {
            container.api.myDeviceAlerts("Bearer $token", limit = 1)
            DiagnosticVerdict.PASS to "Device token accepted by the backend"
        } catch (t: HttpException) {
            if (t.code() == 401 || t.code() == 403) {
                DiagnosticVerdict.FAIL to "Device token rejected (HTTP ${t.code()}) — re-enroll from Settings"
            } else {
                DiagnosticVerdict.WARN to "Unexpected response (HTTP ${t.code()})"
            }
        }
    }

    private suspend fun uploadTest(): Pair<DiagnosticVerdict, String> {
        return when (val outcome = container.syncEngine.sampleAndSync()) {
            is com.sentinelx.mobile.sync.SyncOutcome.Success ->
                DiagnosticVerdict.PASS to "Uploaded ${outcome.uploaded} sample(s)"
            is com.sentinelx.mobile.sync.SyncOutcome.Partial ->
                DiagnosticVerdict.WARN to "Partial: ${outcome.remaining} still queued (${outcome.error})"
            is com.sentinelx.mobile.sync.SyncOutcome.Paused ->
                DiagnosticVerdict.WARN to outcome.reason
            is com.sentinelx.mobile.sync.SyncOutcome.NotEnrolled ->
                DiagnosticVerdict.WARN to "Device not enrolled — nothing to upload"
            is com.sentinelx.mobile.sync.SyncOutcome.Failed ->
                DiagnosticVerdict.FAIL to outcome.error
        }
    }

    private suspend fun databaseTest(): Pair<DiagnosticVerdict, String> {
        val dao = container.queuedMetricDao
        val id = dao.insert(
            QueuedMetric(
                capturedAtEpochMs = 0L,
                cpuPercent = 0.0,
                memoryPercent = 0.0,
                diskPercent = 0.0,
                batterySummary = "diagnostic-probe",
                attempts = Int.MAX_VALUE - 1,
            )
        )
        dao.delete(id)
        return DiagnosticVerdict.PASS to "Room read/write round-trip succeeded"
    }

    private suspend fun workerTest(): Pair<DiagnosticVerdict, String> {
        val infos = WorkManager.getInstance(context)
            .getWorkInfosForUniqueWorkFlow("sentinelx-periodic-sync")
            .first()
        val info = infos.firstOrNull()
            ?: return DiagnosticVerdict.FAIL to "Periodic sync worker is not registered"
        return when (info.state) {
            WorkInfo.State.ENQUEUED, WorkInfo.State.RUNNING ->
                DiagnosticVerdict.PASS to "Periodic sync ${info.state.name.lowercase()} (15-minute cadence)"
            else -> DiagnosticVerdict.WARN to "Worker state: ${info.state.name.lowercase()}"
        }
    }

    private fun notificationTest(): Pair<DiagnosticVerdict, String> {
        val enabled = NotificationManagerCompat.from(context).areNotificationsEnabled()
        return if (enabled) DiagnosticVerdict.PASS to "Notifications enabled"
        else DiagnosticVerdict.WARN to "Notifications disabled — Live Mode status will be invisible"
    }

    private fun batteryOptimisationTest(): Pair<DiagnosticVerdict, String> {
        val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val exempt = pm.isIgnoringBatteryOptimizations(context.packageName)
        return if (exempt) DiagnosticVerdict.PASS to "Exempt from battery optimisation"
        else DiagnosticVerdict.WARN to "Battery optimisation may delay background monitoring — set SentinelX to Unrestricted"
    }

    private fun storageTest(): Pair<DiagnosticVerdict, String> {
        val storage = container.collector.collectStorage()
        val freeMb = storage.availableBytes / (1024 * 1024)
        return when {
            freeMb > 500 -> DiagnosticVerdict.PASS to "$freeMb MB free"
            freeMb > 100 -> DiagnosticVerdict.WARN to "Only $freeMb MB free — telemetry queue may be trimmed"
            else -> DiagnosticVerdict.FAIL to "Critically low storage: $freeMb MB free"
        }
    }

    private suspend fun clockSkewTest(): Pair<DiagnosticVerdict, String> = withContext(Dispatchers.IO) {
        val base = normalizedBase() ?: return@withContext DiagnosticVerdict.FAIL to "No server URL configured"
        val connection = URL("$base/api/v1/health").openConnection() as HttpURLConnection
        connection.connectTimeout = 8000
        connection.connect()
        val dateHeader = connection.getHeaderField("Date")
        connection.disconnect()
        if (dateHeader == null) return@withContext DiagnosticVerdict.WARN to "Server did not send a Date header"
        val serverMs = ZonedDateTime.parse(dateHeader, DateTimeFormatter.RFC_1123_DATE_TIME).toInstant().toEpochMilli()
        val skewSeconds = abs(Instant.now().toEpochMilli() - serverMs) / 1000
        when {
            skewSeconds <= 120 -> DiagnosticVerdict.PASS to "Skew ${skewSeconds}s vs server"
            skewSeconds <= 600 -> DiagnosticVerdict.WARN to "Clock skew ${skewSeconds}s — timestamps may look wrong"
            else -> DiagnosticVerdict.FAIL to "Clock skew ${skewSeconds}s — telemetry history will be misordered"
        }
    }

    private suspend fun serverHost(): String? {
        val base = normalizedBase() ?: return null
        return runCatching { URL(base).host }.getOrNull()
    }

    private suspend fun normalizedBase(): String? =
        HostSelectionInterceptor.normalize(container.stateStore.current().baseUrl)

    companion object {
        fun summaryLine(results: List<DiagnosticResult>): String {
            val passed = results.count { it.verdict == DiagnosticVerdict.PASS }
            val warned = results.count { it.verdict == DiagnosticVerdict.WARN }
            val failed = results.count { it.verdict == DiagnosticVerdict.FAIL }
            return "${results.size} tests: $passed passed, $warned warnings, $failed failed"
        }

        /** Shareable plain-text report; device facts only, no tokens or account data. */
        fun redactedReport(results: List<DiagnosticResult>, agentVersion: String): String = buildString {
            appendLine("SentinelX Android diagnostic report")
            appendLine("Agent: v$agentVersion · ${Build.MANUFACTURER} ${Build.MODEL} · Android ${Build.VERSION.RELEASE}")
            appendLine(summaryLine(results))
            appendLine()
            for (r in results) {
                val mark = when (r.verdict) {
                    DiagnosticVerdict.PASS -> "PASS"
                    DiagnosticVerdict.WARN -> "WARN"
                    DiagnosticVerdict.FAIL -> "FAIL"
                }
                appendLine("[$mark] ${r.name} — ${r.detail} (${r.durationMs} ms)")
            }
        }
    }
}
