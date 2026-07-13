package com.sentinelx.mobile.health

import com.sentinelx.mobile.telemetry.TelemetrySnapshot
import kotlin.math.roundToInt

data class HealthBreakdown(
    val battery: Int,
    val memory: Int,
    val storage: Int,
    val network: Int,
    val agent: Int,
) {
    val overall: Int get() = ((battery + memory + storage + network + agent) / 5.0).roundToInt()

    val status: HealthStatus
        get() = when {
            overall >= 85 -> HealthStatus.HEALTHY
            overall >= 60 -> HealthStatus.WARNING
            else -> HealthStatus.CRITICAL
        }
}

enum class HealthStatus { HEALTHY, WARNING, CRITICAL, OFFLINE }

/**
 * Deterministic, explainable health scoring — every sub-score is 0..100 and
 * the Health screen shows exactly these numbers, so the rules stay simple.
 */
object HealthCalculator {

    fun compute(
        snapshot: TelemetrySnapshot?,
        lastSyncAtEpochMs: Long,
        lastSyncError: String,
        queueDepth: Int,
        nowEpochMs: Long = System.currentTimeMillis(),
    ): HealthBreakdown {
        if (snapshot == null) {
            return HealthBreakdown(battery = 0, memory = 0, storage = 0, network = 0, agent = 0)
        }
        return HealthBreakdown(
            battery = batteryScore(snapshot),
            memory = memoryScore(snapshot),
            storage = storageScore(snapshot),
            network = networkScore(snapshot),
            agent = agentScore(lastSyncAtEpochMs, lastSyncError, queueDepth, nowEpochMs),
        )
    }

    /** Full marks at >=40%; linear below; heat and discharge penalties. */
    fun batteryScore(snapshot: TelemetrySnapshot): Int {
        val b = snapshot.battery
        var score = if (b.levelPercent >= 40) 100 else (b.levelPercent * 2.5).roundToInt()
        val temp = b.temperatureCelsius
        if (temp != null) {
            if (temp >= 45.0) score -= 40 else if (temp >= 40.0) score -= 20
        }
        if (b.isCharging) score += 10
        return score.coerceIn(0, 100)
    }

    /** 100 at <=50% used, sliding to 0 at 100%; low-memory signal caps at 30. */
    fun memoryScore(snapshot: TelemetrySnapshot): Int {
        val used = snapshot.memory.usedPercent
        var score = (100 - ((used - 50).coerceAtLeast(0.0) * 2)).roundToInt()
        if (snapshot.memory.lowMemory) score = score.coerceAtMost(30)
        return score.coerceIn(0, 100)
    }

    /** Storage only matters when it gets tight: 100 at <=80% used, 0 at 100%. */
    fun storageScore(snapshot: TelemetrySnapshot): Int {
        val used = snapshot.storage.usedPercent
        val score = (100 - ((used - 80).coerceAtLeast(0.0) * 5)).roundToInt()
        return score.coerceIn(0, 100)
    }

    fun networkScore(snapshot: TelemetrySnapshot): Int {
        val n = snapshot.network
        var score = when {
            n.isConnected && n.isValidated -> 100
            n.isConnected -> 70
            else -> 10
        }
        if (n.isMetered) score -= 10
        return score.coerceIn(0, 100)
    }

    /** Upload pipeline reliability: sync freshness, error state, backlog. */
    fun agentScore(lastSyncAtEpochMs: Long, lastSyncError: String, queueDepth: Int, nowEpochMs: Long): Int {
        var score = 100
        if (lastSyncError.isNotBlank()) score -= 30
        when {
            lastSyncAtEpochMs <= 0 -> score -= 60
            nowEpochMs - lastSyncAtEpochMs > 2 * 60 * 60 * 1000 -> score -= 40
            nowEpochMs - lastSyncAtEpochMs > 30 * 60 * 1000 -> score -= 20
        }
        when {
            queueDepth > 500 -> score -= 40
            queueDepth > 50 -> score -= 20
        }
        return score.coerceIn(0, 100)
    }
}
