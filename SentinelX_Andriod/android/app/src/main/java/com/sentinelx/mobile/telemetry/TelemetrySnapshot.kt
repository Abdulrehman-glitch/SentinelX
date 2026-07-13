package com.sentinelx.mobile.telemetry

data class BatteryStatus(
    val levelPercent: Int,
    val isCharging: Boolean,
    val plugType: String,
    val temperatureCelsius: Double?,
)

data class MemoryStatus(
    val totalBytes: Long,
    val availableBytes: Long,
    val lowMemory: Boolean,
) {
    val usedPercent: Double
        get() = if (totalBytes <= 0) 0.0 else (totalBytes - availableBytes) * 100.0 / totalBytes
}

data class StorageStatus(
    val totalBytes: Long,
    val availableBytes: Long,
) {
    val usedPercent: Double
        get() = if (totalBytes <= 0) 0.0 else (totalBytes - availableBytes) * 100.0 / totalBytes
}

data class NetworkStatus(
    val isConnected: Boolean,
    val transport: String,
    val isMetered: Boolean,
    val isValidated: Boolean,
)

data class TelemetrySnapshot(
    val capturedAtEpochMs: Long,
    /** Best-effort estimate from CPU frequency scaling; null when sysfs is unreadable. */
    val cpuPercent: Double?,
    val memory: MemoryStatus,
    val storage: StorageStatus,
    val battery: BatteryStatus,
    val network: NetworkStatus,
    /** PowerManager thermal status: none|light|moderate|severe|critical|emergency|shutdown|unsupported. */
    val thermalStatus: String = "unsupported",
) {
    /** Compact summary carried in the heartbeat message (backend metric row has no battery field). */
    fun batterySummary(): String {
        val charge = if (battery.isCharging) "charging(${battery.plugType})" else "discharging"
        val temp = battery.temperatureCelsius?.let { ", %.1fC".format(it) } ?: ""
        return "battery=${battery.levelPercent}% $charge$temp, net=${network.transport}"
    }
}
