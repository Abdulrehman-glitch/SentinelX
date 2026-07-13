package com.sentinelx.mobile.sync

import android.app.Notification
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.sentinelx.mobile.MainActivity
import com.sentinelx.mobile.R
import com.sentinelx.mobile.SentinelXApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Explicit, user-enabled Live Mode: samples and uploads on a short interval
 * behind a visible foreground notification. Reliable 15-minute sync via
 * WorkManager keeps running independently of this service.
 */
class LiveMonitorService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var monitorJob: Job? = null

    // Poked by the network callback so a regained connection flushes the queue
    // immediately instead of waiting out the current (possibly backed-off) delay.
    private val networkRegained = Channel<Unit>(Channel.CONFLATED)
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }

        startAsForeground()
        registerNetworkCallback()

        // A repeated start command (toggle spam, sticky redelivery) must not
        // stack a second sampling loop on top of the running one.
        monitorJob?.cancel()
        val container = (application as SentinelXApp).container
        monitorJob = scope.launch {
            container.stateStore.setLiveModeActive(true)
            val startedAt = System.currentTimeMillis()
            val startMode = container.stateStore.current().monitoringMode
            container.eventLogger.log("monitoring", "info", "Live monitoring started", "Mode: $startMode")
            var consecutiveFailures = 0
            while (isActive) {
                val state = container.stateStore.current()

                // Diagnostic mode samples fast for a bounded window, then stops
                // itself — a 10s cadence must not become a permanent battery drain.
                if (state.monitoringMode == "diagnostic" &&
                    System.currentTimeMillis() - startedAt > DIAGNOSTIC_MAX_MS
                ) {
                    container.eventLogger.log(
                        "monitoring", "info", "Diagnostic session finished",
                        "Auto-stopped after ${DIAGNOSTIC_MAX_MS / 60000} minutes.",
                    )
                    stopSelf()
                    break
                }

                val outcome = try {
                    container.syncEngine.sampleAndSync()
                } catch (t: Throwable) {
                    SyncOutcome.Failed(t.message ?: "sampling error")
                }
                updateNotification(outcome)
                if (outcome is SyncOutcome.Success && outcome.alertsCreated > 0) {
                    notifyAlertsRaised(outcome.alertsCreated)
                }

                consecutiveFailures = when (outcome) {
                    is SyncOutcome.Success, is SyncOutcome.NotEnrolled, is SyncOutcome.Paused -> 0
                    is SyncOutcome.Partial, is SyncOutcome.Failed -> consecutiveFailures + 1
                }

                val baseSeconds = state.modeIntervalSeconds.coerceIn(5, 300)
                if (consecutiveFailures == 0) {
                    // Healthy: drop any stale poke (registering the callback fires
                    // onAvailable immediately) and sleep the configured interval.
                    networkRegained.tryReceive()
                    delay(baseSeconds * 1000L)
                } else {
                    // Back off while the backend is unreachable — hammering a dead
                    // link every 15s wastes battery and floods flaky networks —
                    // but cut the wait short the moment connectivity returns.
                    val backoffSeconds = (baseSeconds * (1 shl minOf(consecutiveFailures, 3)))
                        .coerceAtMost(maxOf(baseSeconds, 120))
                    val wokenByNetwork = withTimeoutOrNull(backoffSeconds * 1000L) {
                        networkRegained.receive()
                    } != null
                    if (wokenByNetwork) consecutiveFailures = 0
                }
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        val container = (application as SentinelXApp).container
        container.eventLogger.log("monitoring", "info", "Live monitoring stopped")
        runBlocking {
            container.stateStore.setLiveModeActive(false)
        }
        unregisterNetworkCallback()
        scope.cancel()
        super.onDestroy()
    }

    private fun registerNetworkCallback() {
        if (networkCallback != null) return
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                networkRegained.trySend(Unit)
            }
        }
        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        cm.registerNetworkCallback(request, callback)
        networkCallback = callback
    }

    private fun unregisterNetworkCallback() {
        val callback = networkCallback ?: return
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        try {
            cm.unregisterNetworkCallback(callback)
        } catch (_: IllegalArgumentException) {
        }
        networkCallback = null
    }

    private fun startAsForeground() {
        val notification = buildNotification("Live monitoring active", "Streaming device telemetry to SentinelX.")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun updateNotification(outcome: SyncOutcome) {
        val text = when (outcome) {
            is SyncOutcome.Success -> "Synced ${outcome.uploaded} sample(s)."
            is SyncOutcome.Partial -> "Partial sync: ${outcome.remaining} queued. ${outcome.error}"
            is SyncOutcome.Failed -> "Offline – queuing locally. ${outcome.error}"
            is SyncOutcome.Paused -> outcome.reason
            is SyncOutcome.NotEnrolled -> "Device not enrolled yet."
        }
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, buildNotification("SentinelX Live Mode", text))
    }

    private fun notifyAlertsRaised(count: Int) {
        val contentIntent = PendingIntent.getActivity(
            this,
            2,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(this, SentinelXApp.ALERTS_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_sentinelx)
            .setContentTitle("SentinelX alert")
            .setContentText("$count alert(s) raised from this device's telemetry.")
            .setContentIntent(contentIntent)
            .setAutoCancel(true)
            .build()
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(ALERT_NOTIFICATION_ID, notification)
    }

    private fun buildNotification(title: String, text: String): Notification {
        val contentIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val stopIntent = PendingIntent.getService(
            this,
            1,
            Intent(this, LiveMonitorService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, SentinelXApp.LIVE_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_sentinelx)
            .setContentTitle(title)
            .setContentText(text)
            .setContentIntent(contentIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .addAction(0, "Stop", stopIntent)
            .build()
    }

    companion object {
        const val ACTION_STOP = "com.sentinelx.mobile.action.STOP_LIVE"
        private const val NOTIFICATION_ID = 4201
        private const val ALERT_NOTIFICATION_ID = 4202
        private const val DIAGNOSTIC_MAX_MS = 10 * 60 * 1000L

        fun start(context: Context) {
            context.startForegroundService(Intent(context, LiveMonitorService::class.java))
        }

        fun stop(context: Context) {
            context.startService(Intent(context, LiveMonitorService::class.java).setAction(ACTION_STOP))
        }
    }
}
