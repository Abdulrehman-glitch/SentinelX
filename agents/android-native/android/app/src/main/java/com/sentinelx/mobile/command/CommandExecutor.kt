package com.sentinelx.mobile.command

import android.content.Context
import com.sentinelx.mobile.data.db.QueuedMetricDao
import com.sentinelx.mobile.data.prefs.AgentStateStore
import com.sentinelx.mobile.sync.LiveMonitorService
import com.sentinelx.mobile.sync.SyncEngine
import com.sentinelx.mobile.sync.SyncOutcome
import com.sentinelx.mobile.sync.TelemetryCollectWorker
import com.sentinelx.mobile.sync.TelemetrySyncWorker
import com.sentinelx.mobile.telemetry.DeviceTelemetryCollector

/**
 * Allowlisted, app-scoped recovery actions. None of these touch other apps,
 * request root, change device-wide settings, or reboot the device — every
 * action operates only within SentinelX's own process/data.
 */
data class ExecutionResult(
    val resultCode: String, // "success" | "failure"
    val message: String,
    val data: Map<String, String> = emptyMap(),
)

class CommandExecutor(
    private val context: Context,
    private val stateStore: AgentStateStore,
    private val syncEngine: SyncEngine,
    private val queuedMetricDao: QueuedMetricDao,
    private val collector: DeviceTelemetryCollector,
) {

    companion object {
        // Mirrors the risk-level assignment seeded server-side by
        // scripts/seed_recovery_policies.py — kept in sync manually.
        val ACTION_RISK_LEVELS: Map<String, String> = mapOf(
            "collect_diagnostics" to "low",
            "retry_telemetry_sync" to "low",
            "reset_api_connection" to "low",
            "repair_local_database" to "low",
            "reschedule_sync_workers" to "low",
            "restart_monitoring_service" to "medium",
            "enter_safe_monitoring_mode" to "medium",
            "restore_normal_monitoring_mode" to "medium",
        )
    }

    suspend fun execute(actionType: String, parameters: Map<String, String>): ExecutionResult {
        return when (actionType) {
            "collect_diagnostics" -> collectDiagnostics()
            "restart_monitoring_service" -> restartMonitoringService()
            "reschedule_sync_workers" -> rescheduleSyncWorkers()
            "retry_telemetry_sync" -> retryTelemetrySync()
            "reset_api_connection" -> resetApiConnection()
            "repair_local_database" -> repairLocalDatabase()
            "enter_safe_monitoring_mode" -> enterSafeMonitoringMode()
            "restore_normal_monitoring_mode" -> restoreNormalMonitoringMode()
            else -> ExecutionResult("failure", "Unknown action '$actionType'.")
        }
    }

    private suspend fun collectDiagnostics(): ExecutionResult {
        val snapshot = collector.collect()
        val state = stateStore.current()
        val queueDepth = queuedMetricDao.count()
        val data = mapOf(
            "cpu_percent" to (snapshot.cpuPercent?.toString() ?: "unknown"),
            "memory_percent" to "%.1f".format(snapshot.memory.usedPercent),
            "disk_percent" to "%.1f".format(snapshot.storage.usedPercent),
            "battery_percent" to snapshot.battery.levelPercent.toString(),
            "thermal_status" to snapshot.thermalStatus,
            "monitoring_mode" to state.monitoringMode,
            "queue_depth" to queueDepth.toString(),
        )
        return ExecutionResult("success", "Diagnostics collected.", data)
    }

    private fun restartMonitoringService(): ExecutionResult {
        return runCatching {
            LiveMonitorService.stop(context)
            LiveMonitorService.start(context)
        }.fold(
            onSuccess = { ExecutionResult("success", "Live monitoring service restarted.") },
            onFailure = { e -> ExecutionResult("failure", "Could not restart monitoring service: ${e.message}") },
        )
    }

    private fun rescheduleSyncWorkers(): ExecutionResult {
        return runCatching {
            TelemetryCollectWorker.schedulePeriodic(context)
            TelemetrySyncWorker.schedulePeriodic(context)
        }.fold(
            onSuccess = { ExecutionResult("success", "Sync workers rescheduled.") },
            onFailure = { e -> ExecutionResult("failure", "Could not reschedule sync workers: ${e.message}") },
        )
    }

    private suspend fun retryTelemetrySync(): ExecutionResult {
        val depthBefore = queuedMetricDao.count()
        return when (val outcome = syncEngine.flush()) {
            is SyncOutcome.Success -> ExecutionResult(
                "success", "Telemetry retry uploaded ${outcome.uploaded} sample(s).",
                mapOf("queue_depth_before" to depthBefore.toString(), "uploaded" to outcome.uploaded.toString()),
            )
            is SyncOutcome.Partial -> ExecutionResult(
                "success", "Telemetry retry partially uploaded ${outcome.uploaded} sample(s), ${outcome.remaining} remaining.",
                mapOf("uploaded" to outcome.uploaded.toString(), "remaining" to outcome.remaining.toString()),
            )
            is SyncOutcome.Paused -> ExecutionResult("success", "Sync paused by policy: ${outcome.reason}.")
            is SyncOutcome.NotEnrolled -> ExecutionResult("failure", "Device is not enrolled.")
            is SyncOutcome.Failed -> ExecutionResult("failure", "Telemetry retry failed: ${outcome.error}")
        }
    }

    private suspend fun resetApiConnection(): ExecutionResult {
        val baseUrl = stateStore.current().baseUrl
        return runCatching {
            com.sentinelx.mobile.data.api.ApiClient.create { baseUrl }.health()
        }.fold(
            onSuccess = { health -> ExecutionResult("success", "API connection confirmed.", mapOf("api_status" to health.apiStatus)) },
            onFailure = { e -> ExecutionResult("failure", "API connection check failed: ${e.message}") },
        )
    }

    private suspend fun repairLocalDatabase(): ExecutionResult {
        val depthBefore = queuedMetricDao.count()
        val dropped = queuedMetricDao.abandonExhausted(maxAttempts = 20)
        val depthAfter = queuedMetricDao.count()
        return ExecutionResult(
            "success",
            "Repaired local database: dropped $dropped exhausted row(s).",
            mapOf(
                "queue_depth_before" to depthBefore.toString(),
                "queue_depth_after" to depthAfter.toString(),
                "dropped" to dropped.toString(),
            ),
        )
    }

    private suspend fun enterSafeMonitoringMode(): ExecutionResult {
        if (stateStore.current().liveModeActive) {
            LiveMonitorService.stop(context)
        }
        stateStore.setMonitoringMode("safe")
        return ExecutionResult("success", "Entered safe monitoring mode (reduced sampling cadence).")
    }

    private suspend fun restoreNormalMonitoringMode(): ExecutionResult {
        stateStore.setMonitoringMode("balanced")
        return ExecutionResult("success", "Restored normal (balanced) monitoring mode.")
    }
}
