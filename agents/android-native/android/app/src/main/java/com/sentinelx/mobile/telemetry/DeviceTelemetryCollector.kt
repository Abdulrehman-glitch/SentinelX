package com.sentinelx.mobile.telemetry

import android.annotation.SuppressLint
import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.provider.Settings
import java.io.File
import java.util.Locale

class DeviceTelemetryCollector(private val context: Context) {

    fun collect(): TelemetrySnapshot = TelemetrySnapshot(
        capturedAtEpochMs = System.currentTimeMillis(),
        cpuPercent = CpuEstimator.estimatePercent(),
        memory = collectMemory(),
        storage = collectStorage(),
        battery = collectBattery(),
        network = collectNetwork(),
        thermalStatus = collectThermal(),
    )

    fun collectThermal(): String {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return "unsupported"
        val pm = context.getSystemService(Context.POWER_SERVICE) as android.os.PowerManager
        return when (pm.currentThermalStatus) {
            android.os.PowerManager.THERMAL_STATUS_NONE -> "none"
            android.os.PowerManager.THERMAL_STATUS_LIGHT -> "light"
            android.os.PowerManager.THERMAL_STATUS_MODERATE -> "moderate"
            android.os.PowerManager.THERMAL_STATUS_SEVERE -> "severe"
            android.os.PowerManager.THERMAL_STATUS_CRITICAL -> "critical"
            android.os.PowerManager.THERMAL_STATUS_EMERGENCY -> "emergency"
            android.os.PowerManager.THERMAL_STATUS_SHUTDOWN -> "shutdown"
            else -> "unsupported"
        }
    }

    fun collectMemory(): MemoryStatus {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val info = ActivityManager.MemoryInfo()
        am.getMemoryInfo(info)
        return MemoryStatus(totalBytes = info.totalMem, availableBytes = info.availMem, lowMemory = info.lowMemory)
    }

    fun collectStorage(): StorageStatus {
        val stat = StatFs(Environment.getDataDirectory().path)
        return StorageStatus(totalBytes = stat.totalBytes, availableBytes = stat.availableBytes)
    }

    fun collectBattery(): BatteryStatus {
        val intent: Intent? = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = intent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = intent?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        // Sticky-intent extras can be missing on first read; BatteryManager is the fallback
        // so an unknown level doesn't render as an alarming 0%.
        val percent = if (level >= 0 && scale > 0) {
            level * 100 / scale
        } else {
            val bm = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
            bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY).coerceIn(0, 100)
        }

        val status = intent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val charging = status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL

        val plug = when (intent?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) {
            BatteryManager.BATTERY_PLUGGED_AC -> "ac"
            BatteryManager.BATTERY_PLUGGED_USB -> "usb"
            BatteryManager.BATTERY_PLUGGED_WIRELESS -> "wireless"
            else -> "none"
        }

        val tempTenths = intent?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE) ?: Int.MIN_VALUE
        val temperature = if (tempTenths != Int.MIN_VALUE) tempTenths / 10.0 else null

        return BatteryStatus(levelPercent = percent, isCharging = charging, plugType = plug, temperatureCelsius = temperature)
    }

    fun collectNetwork(): NetworkStatus {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val caps = cm.activeNetwork?.let { cm.getNetworkCapabilities(it) }
            ?: return NetworkStatus(isConnected = false, transport = "none", isMetered = false, isValidated = false)

        val transport = when {
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) -> "vpn"
            else -> "other"
        }

        return NetworkStatus(
            isConnected = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),
            transport = transport,
            isMetered = !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED),
            isValidated = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED),
        )
    }

    /** Stable per-install identity used as the SentinelX hostname; survives app restarts. */
    @SuppressLint("HardwareIds")
    fun stableHostname(): String {
        val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: "unknown"
        val modelSlug = Build.MODEL.lowercase(Locale.US).replace(Regex("[^a-z0-9]+"), "-").trim('-')
        return "android-$modelSlug-${androidId.take(8)}"
    }

    fun displayName(): String = "${Build.MANUFACTURER} ${Build.MODEL}"

    fun osName(): String = "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})"
}

/**
 * Device-wide CPU load is not readable on modern Android (/proc/stat is
 * restricted since O). Approximate it from per-core frequency scaling:
 * current/max frequency averaged over cores. Returns null when sysfs is hidden.
 */
object CpuEstimator {

    fun estimatePercent(): Double? {
        val cpuDirs = File("/sys/devices/system/cpu")
            .listFiles { f -> f.isDirectory && f.name.matches(Regex("cpu\\d+")) }
            ?: return null

        var ratioSum = 0.0
        var counted = 0

        for (dir in cpuDirs) {
            val cur = readLong(File(dir, "cpufreq/scaling_cur_freq")) ?: continue
            val max = readLong(File(dir, "cpufreq/cpuinfo_max_freq")) ?: continue
            if (max <= 0) continue
            ratioSum += cur.toDouble() / max.toDouble()
            counted++
        }

        if (counted == 0) return null
        return (ratioSum / counted * 100.0).coerceIn(0.0, 100.0)
    }

    private fun readLong(file: File): Long? = try {
        if (file.canRead()) file.readText().trim().toLongOrNull() else null
    } catch (_: Exception) {
        null
    }
}
