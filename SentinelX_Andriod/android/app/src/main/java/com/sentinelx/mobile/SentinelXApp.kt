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
        createLiveChannel()
        // Safe to schedule unconditionally: the worker no-ops until enrollment.
        TelemetrySyncWorker.schedulePeriodic(this)
    }

    private fun createLiveChannel() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            LIVE_CHANNEL_ID,
            getString(R.string.live_channel_name),
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = getString(R.string.live_channel_description)
        }
        nm.createNotificationChannel(channel)
    }

    companion object {
        const val LIVE_CHANNEL_ID = "sentinelx_live"
    }
}
