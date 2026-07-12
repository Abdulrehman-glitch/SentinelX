package com.sentinelx.mobile

import com.sentinelx.mobile.telemetry.BatteryStatus
import com.sentinelx.mobile.telemetry.MemoryStatus
import com.sentinelx.mobile.telemetry.NetworkStatus
import com.sentinelx.mobile.telemetry.StorageStatus
import com.sentinelx.mobile.telemetry.TelemetrySnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TelemetrySnapshotTest {

    @Test
    fun `memory used percent from totals`() {
        val memory = MemoryStatus(totalBytes = 8_000, availableBytes = 2_000, lowMemory = false)
        assertEquals(75.0, memory.usedPercent, 0.001)
    }

    @Test
    fun `zero total memory does not divide by zero`() {
        val memory = MemoryStatus(totalBytes = 0, availableBytes = 0, lowMemory = false)
        assertEquals(0.0, memory.usedPercent, 0.001)
    }

    @Test
    fun `storage used percent from totals`() {
        val storage = StorageStatus(totalBytes = 100, availableBytes = 15)
        assertEquals(85.0, storage.usedPercent, 0.001)
    }

    @Test
    fun `battery summary reports charging state and transport`() {
        val snapshot = snapshotWith(
            battery = BatteryStatus(levelPercent = 76, isCharging = true, plugType = "usb", temperatureCelsius = 30.4),
            network = NetworkStatus(isConnected = true, transport = "wifi", isMetered = false, isValidated = true),
        )
        val summary = snapshot.batterySummary()
        assertTrue(summary.contains("battery=76%"))
        assertTrue(summary.contains("charging(usb)"))
        assertTrue(summary.contains("30.4C"))
        assertTrue(summary.contains("net=wifi"))
    }

    @Test
    fun `battery summary omits temperature when unavailable`() {
        val snapshot = snapshotWith(
            battery = BatteryStatus(levelPercent = 40, isCharging = false, plugType = "none", temperatureCelsius = null),
            network = NetworkStatus(isConnected = false, transport = "none", isMetered = false, isValidated = false),
        )
        val summary = snapshot.batterySummary()
        assertTrue(summary.contains("discharging"))
        assertTrue(!summary.contains("C,"))
    }

    private fun snapshotWith(battery: BatteryStatus, network: NetworkStatus) = TelemetrySnapshot(
        capturedAtEpochMs = 0L,
        cpuPercent = null,
        memory = MemoryStatus(1, 1, false),
        storage = StorageStatus(1, 1),
        battery = battery,
        network = network,
    )
}
