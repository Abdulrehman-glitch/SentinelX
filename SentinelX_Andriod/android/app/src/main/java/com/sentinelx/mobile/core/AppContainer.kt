package com.sentinelx.mobile.core

import android.content.Context
import com.sentinelx.mobile.data.api.ApiClient
import com.sentinelx.mobile.data.api.SentinelXApi
import com.sentinelx.mobile.data.db.AppDatabase
import com.sentinelx.mobile.data.prefs.AgentStateStore
import com.sentinelx.mobile.data.prefs.SecureStore
import com.sentinelx.mobile.data.repo.AuthRepository
import com.sentinelx.mobile.data.repo.EnrollmentRepository
import com.sentinelx.mobile.sync.SyncEngine
import com.sentinelx.mobile.telemetry.DeviceTelemetryCollector
import kotlinx.coroutines.runBlocking

/** Hand-rolled DI: one graph for the whole process (UI, worker, service). */
class AppContainer(context: Context) {

    val stateStore = AgentStateStore(context)
    val secureStore = SecureStore(context)
    val collector = DeviceTelemetryCollector(context)

    private val database = AppDatabase.build(context)
    val queuedMetricDao = database.queuedMetricDao()
    val agentEventDao = database.agentEventDao()
    val eventLogger = EventLogger(agentEventDao)

    // The interceptor reads the persisted base URL on every request; cheap enough
    // at our sampling rates and always consistent with what the user saved.
    val api: SentinelXApi = ApiClient.create {
        runBlocking { stateStore.current().baseUrl }
    }

    val authRepository = AuthRepository(api, stateStore, secureStore)
    val enrollmentRepository = EnrollmentRepository(api, stateStore, secureStore, collector)
    val syncEngine = SyncEngine(api, queuedMetricDao, stateStore, secureStore, collector, eventLogger)
}
