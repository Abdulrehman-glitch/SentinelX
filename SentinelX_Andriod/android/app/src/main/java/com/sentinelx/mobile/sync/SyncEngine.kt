package com.sentinelx.mobile.sync

import com.sentinelx.mobile.data.api.ApiClient
import com.sentinelx.mobile.data.api.SentinelXApi
import com.sentinelx.mobile.data.api.dto.HeartbeatRequest
import com.sentinelx.mobile.data.api.dto.MetricRequest
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

sealed interface SyncOutcome {
    data class Success(val uploaded: Int, val alertsCreated: Int) : SyncOutcome
    data class Partial(val uploaded: Int, val remaining: Int, val error: String) : SyncOutcome
    data class Failed(val error: String) : SyncOutcome
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
) {

    private val flushMutex = Mutex()

    suspend fun sampleAndQueue(): TelemetrySnapshot {
        val snapshot = collector.collect()
        dao.insert(
            QueuedMetric(
                capturedAtEpochMs = snapshot.capturedAtEpochMs,
                cpuPercent = snapshot.cpuPercent ?: 0.0,
                memoryPercent = snapshot.memory.usedPercent.coerceIn(0.0, 100.0),
                diskPercent = snapshot.storage.usedPercent.coerceIn(0.0, 100.0),
                batterySummary = snapshot.batterySummary(),
            )
        )
        dao.trimToNewest(MAX_QUEUE_ROWS)
        return snapshot
    }

    suspend fun flush(): SyncOutcome = flushMutex.withLock {
        val state = stateStore.current()
        val deviceId = state.deviceId
        val token = secureStore.deviceToken

        if (deviceId.isBlank() || token.isNullOrBlank()) {
            return@withLock SyncOutcome.NotEnrolled
        }

        val auth = "Bearer $token"
        var uploaded = 0
        var alertsCreated = 0

        dao.abandonExhausted(MAX_ATTEMPTS)

        while (true) {
            val batch = dao.oldestPending(BATCH_SIZE)
            if (batch.isEmpty()) break

            for (row in batch) {
                try {
                    val response = api.ingestMetric(
                        auth,
                        MetricRequest(
                            deviceId = deviceId,
                            cpuPercent = row.cpuPercent,
                            memoryPercent = row.memoryPercent,
                            diskPercent = row.diskPercent,
                        ),
                    )
                    dao.delete(row.id)
                    uploaded++
                    alertsCreated += response.alertsCreated
                } catch (t: Throwable) {
                    dao.incrementAttempts(row.id)
                    val message = ApiClient.readableError(t)
                    val fatalAuth = t is HttpException && (t.code() == 401 || t.code() == 403)
                    val error = if (fatalAuth) "Device token rejected ($message). Re-enroll from Settings." else message
                    stateStore.recordSyncResult(
                        successAtEpochMs = if (uploaded > 0) System.currentTimeMillis() else null,
                        error = error,
                        alertsCreated = alertsCreated,
                    )
                    val remaining = dao.count()
                    return@withLock if (uploaded > 0) {
                        SyncOutcome.Partial(uploaded, remaining, error)
                    } else {
                        SyncOutcome.Failed(error)
                    }
                }
            }
        }

        // One heartbeat per successful flush cycle carries battery/network context.
        try {
            val snapshot = collector.collect()
            api.sendHeartbeat(
                auth,
                HeartbeatRequest(deviceId = deviceId, status = "online", message = snapshot.batterySummary()),
            )
        } catch (_: IOException) {
            // Metrics made it; a dropped heartbeat is not a sync failure.
        } catch (_: HttpException) {
        }

        stateStore.recordSyncResult(
            successAtEpochMs = System.currentTimeMillis(),
            error = null,
            alertsCreated = alertsCreated,
        )
        SyncOutcome.Success(uploaded, alertsCreated)
    }

    suspend fun sampleAndSync(): SyncOutcome {
        sampleAndQueue()
        return flush()
    }

    private companion object {
        const val BATCH_SIZE = 50
        const val MAX_QUEUE_ROWS = 2000
        const val MAX_ATTEMPTS = 50
    }
}
