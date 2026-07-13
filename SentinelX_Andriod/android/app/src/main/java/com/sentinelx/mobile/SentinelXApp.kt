package com.sentinelx.mobile

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import com.sentinelx.mobile.core.AppContainer
import com.sentinelx.mobile.sync.TelemetrySyncWorker

class SentinelXApp : Application() {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        createChannels()
        // Safe to schedule unconditionally: the worker no-ops until enrollment.
        TelemetrySyncWorker.schedulePeriodic(this)
    }

    private fun createChannels() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(
                LIVE_CHANNEL_ID,
                getString(R.string.live_channel_name),
                NotificationManager.IMPORTANCE_LOW,
            ).apply { description = getString(R.string.live_channel_description) }
        )
        nm.createNotificationChannel(
            NotificationChannel(
                ALERTS_CHANNEL_ID,
                getString(R.string.alerts_channel_name),
                NotificationManager.IMPORTANCE_HIGH,
            ).apply { description = getString(R.string.alerts_channel_description) }
        )
        nm.createNotificationChannel(
            NotificationChannel(
                RECOVERY_CHANNEL_ID,
                getString(R.string.recovery_channel_name),
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply { description = getString(R.string.recovery_channel_description) }
        )
    }

    companion object {
        const val LIVE_CHANNEL_ID = "sentinelx_live"
        const val ALERTS_CHANNEL_ID = "sentinelx_alerts"
        const val RECOVERY_CHANNEL_ID = "sentinelx_recovery"
    }
}
