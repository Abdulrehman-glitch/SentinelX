package com.sentinelx.mobile

import com.sentinelx.mobile.health.HealthCalculator
import com.sentinelx.mobile.health.HealthStatus
import com.sentinelx.mobile.telemetry.BatteryStatus
import com.sentinelx.mobile.telemetry.MemoryStatus
import com.sentinelx.mobile.telemetry.NetworkStatus
import com.sentinelx.mobile.telemetry.StorageStatus
import com.sentinelx.mobile.telemetry.TelemetrySnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HealthCalculatorTest {

    private fun snapshot(
        batteryLevel: Int = 80,
        charging: Boolean = false,
        temp: Double? = 25.0,
        memUsedPercent: Double = 40.0,
        lowMemory: Boolean = false,
        storageUsedPercent: Double = 50.0,
        connected: Boolean = true,
        validated: Boolean = true,
        metered: Boolean = false,
    ): TelemetrySnapshot {
        val total = 100L
        return TelemetrySnapshot(
            capturedAtEpochMs = 0,
            cpuPercent = 50.0,
            memory = MemoryStatus(total, (total * (100 - memUsedPercent) / 100).toLong(), lowMemory),
            storage = StorageStatus(total, (total * (100 - storageUsedPercent) / 100).toLong()),
            battery = BatteryStatus(batteryLevel, charging, "none", temp),
            network = NetworkStatus(connected, "wifi", metered, validated),
        )
    }

    @Test
    fun healthyDeviceScoresHigh() {
        val hb = HealthCalculator.compute(snapshot(), lastSyncAtEpochMs = 1_000, lastSyncError = "", queueDepth = 0, nowEpochMs = 2_000)
        assertEquals(100, hb.battery)
        assertEquals(100, hb.memory)
        assertEquals(100, hb.storage)
        assertEquals(100, hb.network)
        assertEquals(100, hb.agent)
        assertEquals(HealthStatus.HEALTHY, hb.status)
    }

    @Test
    fun lowBatteryScalesLinearly() {
        assertEquals(50, HealthCalculator.batteryScore(snapshot(batteryLevel = 20)))
        assertEquals(100, HealthCalculator.batteryScore(snapshot(batteryLevel = 40)))
    }

    @Test
    fun hotBatteryIsPenalized() {
        assertEquals(80, HealthCalculator.batteryScore(snapshot(temp = 41.0)))
        assertEquals(60, HealthCalculator.batteryScore(snapshot(temp = 46.0)))
    }

    @Test
    fun chargingSoftensLowBattery() {
        val discharging = HealthCalculator.batteryScore(snapshot(batteryLevel = 10))
        val charging = HealthCalculator.batteryScore(snapshot(batteryLevel = 10, charging = true))
        assertEquals(discharging + 10, charging)
    }

    @Test
    fun memoryPressureDropsScore() {
        assertEquals(100, HealthCalculator.memoryScore(snapshot(memUsedPercent = 50.0)))
        assertEquals(30, HealthCalculator.memoryScore(snapshot(memUsedPercent = 85.0)))
        assertEquals(0, HealthCalculator.memoryScore(snapshot(memUsedPercent = 100.0)))
    }

    @Test
    fun lowMemoryFlagCapsScore() {
        assertTrue(HealthCalculator.memoryScore(snapshot(memUsedPercent = 40.0, lowMemory = true)) <= 30)
    }

    @Test
    fun storageOnlyMattersWhenTight() {
        assertEquals(100, HealthCalculator.storageScore(snapshot(storageUsedPercent = 80.0)))
        assertEquals(50, HealthCalculator.storageScore(snapshot(storageUsedPercent = 90.0)))
        assertEquals(0, HealthCalculator.storageScore(snapshot(storageUsedPercent = 100.0)))
    }

    @Test
    fun unvalidatedAndDisconnectedNetworksScoreLower() {
        assertEquals(70, HealthCalculator.networkScore(snapshot(validated = false)))
        assertEquals(10, HealthCalculator.networkScore(snapshot(connected = false, validated = false)))
        assertEquals(90, HealthCalculator.networkScore(snapshot(metered = true)))
    }

    @Test
    fun agentScorePenalizesStaleSyncAndBacklog() {
        val now = 10_000_000_000L
        assertEquals(100, HealthCalculator.agentScore(now - 60_000, "", 0, now))
        assertEquals(80, HealthCalculator.agentScore(now - 31 * 60 * 1000, "", 0, now))
        assertEquals(60, HealthCalculator.agentScore(now - 3 * 60 * 60 * 1000, "", 0, now))
        assertEquals(40, HealthCalculator.agentScore(0, "", 0, now))
        assertEquals(50, HealthCalculator.agentScore(now - 60_000, "connection refused", 50 + 1, now))
        assertEquals(30, HealthCalculator.agentScore(now - 60_000, "connection refused", 501, now))
    }

    @Test
    fun missingSnapshotIsAllZeros() {
        val hb = HealthCalculator.compute(null, 0, "", 0, 0)
        assertEquals(0, hb.overall)
        assertEquals(HealthStatus.CRITICAL, hb.status)
    }
}
