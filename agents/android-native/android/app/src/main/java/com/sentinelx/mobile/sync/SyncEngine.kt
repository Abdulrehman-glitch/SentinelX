package com.sentinelx.mobile.sync

import com.sentinelx.mobile.core.EventLogger
import com.sentinelx.mobile.data.api.ApiClient
import com.sentinelx.mobile.data.api.SentinelXApi
import com.sentinelx.mobile.data.api.dto.HeartbeatRequest
import com.sentinelx.mobile.data.api.dto.MetricBatchRequest
import com.sentinelx.mobile.data.api.dto.MetricSampleDto
import com.sentinelx.mobile.data.db.QueuedMetric
import com.sentinelx.mobile.data.db.QueuedMetricDao
import com.sentinelx.mobile.data.prefs.AgentStateStore
import com.sentinelx.mobile.data.prefs.SecureStore
import com.sentinelx.mobile.telemetry.DeviceTelemetryCollector
import com.sentinelx.mobile.telemetry.TelemetrySnapshot
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import retrofit2.HttpException
import java.io.IOException
import java.time.Instant
import java.util.UUID

sealed interface SyncOutcome {
    data class Success(val uploaded: Int, val alertsCreated: Int) : SyncOutcome
    data class Partial(val uploaded: Int, val remaining: Int, val error: String) : SyncOutcome
    data class Failed(val error: String) : SyncOutcome
    data class Paused(val reason: String) : SyncOutcome
    data object NotEnrolled : SyncOutcome
}

/**
 * Single owner of the collect → queue → upload path. Both the WorkManager
 * worker and the Live Mode service call into this, serialized by a mutex so
 * concurrent flushes cannot double-send queue rows.
 */
class SyncEngine(
    private val api: SentinelXApi,
    private val dao: QueuedMetricDao,
    private val stateStore: AgentStateStore,
    private val secureStore: SecureStore,
    private val collector: DeviceTelemetryCollector,
    private val events: EventLogger,
) {

    private val flushMutex = Mutex()

    suspend fun sampleAndQueue(): TelemetrySnapshot {
        val snapshot = collector.collect()
        dao.insert(
            QueuedMetric(
                capturedAtEpochMs = snapshot.capturedAtEpochMs,
                eventId = UUID.randomUUID().toString(),
                // -1 sentinel = unreadable CPU; uploaded as null, never as 0%.
                cpuPercent = snapshot.cpuPercent ?: -1.0,
                memoryPercent = snapshot.memory.usedPercent.coerceIn(0.0, 100.0),
                diskPercent = snapshot.storage.usedPercent.coerceIn(0.0, 100.0),
                batterySummary = snapshot.batterySummary(),
                batteryPercent = snapshot.battery.levelPercent,
                batteryCharging = snapshot.battery.isCharging,
                networkTransport = snapshot.network.transport,
                batteryTemperatureC = snapshot.battery.temperatureCelsius,
                thermalStatus = snapshot.thermalStatus,
                networkValidated = snapshot.network.isValidated,
                networkMetered = snapshot.network.isMetered,
            )
        )
        dao.trimToNewest(MAX_QUEUE_ROWS)
        return snapshot
    }

    /** Policy gate shared by the worker and Live Mode before touching the network. */
    private suspend fun uploadPolicyBlock(snapshot: TelemetrySnapshot?): String? {
        val state = stateStore.current()
        val current = snapshot ?: collector.collect()
        if (state.pauseOnLowBattery && current.battery.levelPercent < LOW_BATTERY_PERCENT && !current.battery.isCharging) {
            return "Paused: battery below $LOW_BATTERY_PERCENT% and not charging"
        }
        if (state.wifiOnlyUploads && current.network.transport != "wifi") {
            return "Waiting for Wi-Fi (uploads restricted to Wi-Fi)"
        }
        return null
    }

    suspend fun flush(snapshot: TelemetrySnapshot? = null): SyncOutcome = flushMutex.withLock {
        val state = stateStore.current()
        val deviceId = state.deviceId
        val token = secureStore.deviceToken

        if (deviceId.isBlank() || token.isNullOrBlank()) {
            return@withLock SyncOutcome.NotEnrolled
        }

        uploadPolicyBlock(snapshot)?.let { reason ->
            return@withLock SyncOutcome.Paused(reason)
        }

        val hadError = state.lastSyncError.isNotBlank()
        val auth = "Bearer $token"
        var uploaded = 0
        var alertsCreated = 0
        var latencyMs: Long? = null

        dao.abandonExhausted(MAX_ATTEMPTS)

        while (true) {
            val batch = dao.oldestPending(BATCH_SIZE)
            if (batch.isEmpty()) break

            try {
                val startedAt = System.currentTimeMillis()
                val response = api.ingestMetricBatch(
                    auth,
                    MetricBatchRequest(deviceId, batch.map { it.toSampleDto(latencyMs ?: state.lastLatencyMs) }),
                )
                if (latencyMs == null) latencyMs = System.currentTimeMillis() - startedAt
                // stored + duplicates are both backend-acknowledged — safe to delete.
                batch.forEach { dao.delete(it.id) }
                uploaded += response.stored + response.duplicates
                alertsCreated += response.alertsCreated
            } catch (t: Throwable) {
                batch.forEach { dao.incrementAttempts(it.id) }
                val message = ApiClient.readableError(t)
                val fatalAuth = t is HttpException && (t.code() == 401 || t.code() == 403)
                val error = if (fatalAuth) "Device token rejected ($message). Re-enroll from Settings." else message
                stateStore.recordSyncResult(
                    successAtEpochMs = if (uploaded > 0) System.currentTimeMillis() else null,
                    error = error,
                    alertsCreated = alertsCreated,
                    latencyMs = latencyMs,
                )
                if (!hadError) {
                    events.log("connection", if (fatalAuth) "critical" else "warning", "Telemetry upload failing", error)
                }
                val remaining = dao.count()
                return@withLock if (uploaded > 0) {
                    SyncOutcome.Partial(uploaded, remaining, error)
                } else {
                    SyncOutcome.Failed(error)
                }
            }
        }

        // One heartbeat per successful flush cycle carries battery/network context.
        try {
            val current = snapshot ?: collector.collect()
            api.sendHeartbeat(
                auth,
                HeartbeatRequest(deviceId = deviceId, status = "online", message = current.batterySummary()),
            )
        } catch (_: IOException) {
            // Metrics made it; a dropped heartbeat is not a sync failure.
        } catch (_: HttpException) {
        }

        stateStore.recordSyncResult(
            successAtEpochMs = System.currentTimeMillis(),
            error = null,
            alertsCreated = alertsCreated,
            latencyMs = latencyMs,
        )
        if (hadError && uploaded > 0) {
            events.log("connection", "info", "Connection restored", "Flushed $uploaded queued sample(s) to the backend.")
        }
        if (alertsCreated > 0) {
            events.log("alerts", "warning", "Backend raised $alertsCreated alert(s)", "Triggered by this device's latest telemetry.")
        }
        SyncOutcome.Success(uploaded, alertsCreated)
    }

    suspend fun sampleAndSync(): SyncOutcome {
        val snapshot = sampleAndQueue()
        return flush(snapshot)
    }

    private fun QueuedMetric.toSampleDto(lastLatencyMs: Long?) = MetricSampleDto(
        eventId = eventId.ifBlank { null },
        cpuPercent = if (cpuPercent < 0) null else cpuPercent,
        memoryPercent = memoryPercent,
        diskPercent = diskPercent,
        batteryPercent = if (batteryPercent in 0..100) batteryPercent.toDouble() else null,
        batteryCharging = if (batteryPercent in 0..100) batteryCharging else null,
        batteryTemperatureC = batteryTemperatureC,
        thermalStatus = thermalStatus.ifBlank { null }?.takeIf { it != "unsupported" },
        networkTransport = networkTransport.ifBlank { null },
        networkValidated = networkValidated,
        networkMetered = networkMetered,
        latencyMs = lastLatencyMs?.takeIf { it > 0 }?.toDouble(),
        recordedAt = Instant.ofEpochMilli(capturedAtEpochMs).toString(),
    )

    private companion object {
        const val BATCH_SIZE = 100
        const val MAX_QUEUE_ROWS = 2000
        const val MAX_ATTEMPTS = 50
        const val LOW_BATTERY_PERCENT = 15
    }
}
