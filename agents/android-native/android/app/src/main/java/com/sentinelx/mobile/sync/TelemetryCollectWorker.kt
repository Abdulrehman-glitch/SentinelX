package com.sentinelx.mobile.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.sentinelx.mobile.SentinelXApp
import java.util.concurrent.TimeUnit

/**
 * Periodic sampling with NO network constraint: the phone keeps building
 * offline history while disconnected, which is exactly when monitoring data
 * matters most. Uploading is TelemetrySyncWorker's job (network-constrained).
 */
class TelemetryCollectWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val container = (applicationContext as SentinelXApp).container
        if (!container.stateStore.current().isEnrolled) return Result.success()

        return try {
            container.syncEngine.sampleAndQueue()
            // Opportunistic flush attempt; WorkManager holds it until a network exists.
            TelemetrySyncWorker.syncNow(applicationContext)
            Result.success()
        } catch (_: Throwable) {
            // A failed sample must not kill periodic collection.
            Result.success()
        }
    }

    companion object {
        private const val PERIODIC_NAME = "sentinelx-periodic-collect"

        fun schedulePeriodic(context: Context) {
            val request = PeriodicWorkRequestBuilder<TelemetryCollectWorker>(15, TimeUnit.MINUTES).build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }
    }
}
