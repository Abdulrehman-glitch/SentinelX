package com.sentinelx.mobile.command

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.sentinelx.mobile.SentinelXApp
import java.util.concurrent.TimeUnit

/**
 * Polls for signed recovery commands. No-ops until the device is enrolled
 * (CommandRepository.pollAndExecute() checks the device token itself, same
 * pattern as SyncEngine). Scheduled unconditionally alongside the two
 * telemetry workers — safe because it's a pure no-op pre-enrolment.
 */
class CommandPollWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val container = (applicationContext as SentinelXApp).container
        return runCatching {
            container.commandRepository.reportCapabilities()
            container.commandRepository.pollAndExecute()
        }.fold(
            onSuccess = { Result.success() },
            onFailure = { if (runAttemptCount < 5) Result.retry() else Result.failure() },
        )
    }

    companion object {
        private const val PERIODIC_NAME = "sentinelx-command-poll"

        private val networkConstraint =
            Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

        fun schedulePeriodic(context: Context) {
            val request = PeriodicWorkRequestBuilder<CommandPollWorker>(15, TimeUnit.MINUTES)
                .setConstraints(networkConstraint)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }
    }
}
