package com.sentinelx.mobile.sync

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.sentinelx.mobile.SentinelXApp
import java.util.concurrent.TimeUnit

/**
 * Durable upload path: flushes whatever TelemetryCollectWorker (or Live Mode)
 * has queued. Sampling was deliberately split out so an offline device still
 * builds history while this worker waits for connectivity.
 */
class TelemetrySyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val container = (applicationContext as SentinelXApp).container
        return when (val outcome = container.syncEngine.flush()) {
            is SyncOutcome.Success -> Result.success()
            is SyncOutcome.NotEnrolled -> Result.success()
            // Policy pause (low battery / waiting for Wi-Fi): the sample stays
            // queued; the next periodic run uploads it. Not a failure.
            is SyncOutcome.Paused -> Result.success()
            is SyncOutcome.Partial -> Result.retry()
            is SyncOutcome.Failed ->
                if (runAttemptCount < 5) Result.retry() else Result.failure()
        }
    }

    companion object {
        private const val PERIODIC_NAME = "sentinelx-periodic-sync"
        private const val ONESHOT_NAME = "sentinelx-sync-now"

        private val networkConstraint =
            Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

        fun schedulePeriodic(context: Context) {
            val request = PeriodicWorkRequestBuilder<TelemetrySyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(networkConstraint)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }

        fun syncNow(context: Context) {
            val request = OneTimeWorkRequestBuilder<TelemetrySyncWorker>()
                .setConstraints(networkConstraint)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                ONESHOT_NAME,
                ExistingWorkPolicy.REPLACE,
                request,
            )
        }
    }
}
