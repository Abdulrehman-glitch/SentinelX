package com.sentinelx.mobile.ui

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.sentinelx.mobile.core.AppContainer
import com.sentinelx.mobile.data.api.ApiClient
import com.sentinelx.mobile.data.api.dto.AlertDto
import com.sentinelx.mobile.data.db.AgentEvent
import com.sentinelx.mobile.data.prefs.AgentState
import com.sentinelx.mobile.diagnostics.DiagnosticResult
import com.sentinelx.mobile.diagnostics.DiagnosticsRunner
import com.sentinelx.mobile.health.HealthBreakdown
import com.sentinelx.mobile.health.HealthCalculator
import com.sentinelx.mobile.sync.LiveMonitorService
import com.sentinelx.mobile.sync.SyncOutcome
import com.sentinelx.mobile.sync.TelemetrySyncWorker
import com.sentinelx.mobile.telemetry.TelemetrySnapshot
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class UiFlags(
    val loginInProgress: Boolean = false,
    val loginError: String? = null,
    val enrollInProgress: Boolean = false,
    val enrollError: String? = null,
    val manualSyncInProgress: Boolean = false,
    val manualSyncResult: String? = null,
    val connectionTestInProgress: Boolean = false,
    val connectionTestResult: String? = null,
    val alertsRefreshing: Boolean = false,
    val alertsError: String? = null,
    val diagnosticsRunning: Boolean = false,
)

/** One ViewModel drives the whole shell; screens are thin views over it. */
class AgentViewModel(
    private val container: AppContainer,
    private val appContext: Context,
) : ViewModel() {

    val agentState: StateFlow<AgentState?> = container.stateStore.state
        .stateIn(viewModelScope, SharingStarted.Eagerly, null)

    val queueDepth: StateFlow<Int> = container.queuedMetricDao.countFlow()
        .stateIn(viewModelScope, SharingStarted.Eagerly, 0)

    private val _flags = MutableStateFlow(UiFlags())
    val flags: StateFlow<UiFlags> = _flags.asStateFlow()

    private val _snapshot = MutableStateFlow<TelemetrySnapshot?>(null)
    val snapshot: StateFlow<TelemetrySnapshot?> = _snapshot.asStateFlow()

    /** Rolling window of recent local samples for sparklines (newest last). */
    private val _snapshotHistory = MutableStateFlow<List<TelemetrySnapshot>>(emptyList())
    val snapshotHistory: StateFlow<List<TelemetrySnapshot>> = _snapshotHistory.asStateFlow()

    private val _alerts = MutableStateFlow<List<AlertDto>>(emptyList())
    val alerts: StateFlow<List<AlertDto>> = _alerts.asStateFlow()

    private val _diagnostics = MutableStateFlow<List<DiagnosticResult>>(emptyList())
    val diagnostics: StateFlow<List<DiagnosticResult>> = _diagnostics.asStateFlow()

    val health: StateFlow<HealthBreakdown> =
        combine(_snapshot, container.stateStore.state, container.queuedMetricDao.countFlow()) { snap, state, queue ->
            HealthCalculator.compute(snap, state.lastSyncAtEpochMs, state.lastSyncError, queue)
        }.stateIn(viewModelScope, SharingStarted.Eagerly, HealthCalculator.compute(null, 0, "", 0))

    init {
        // Local dashboard refresh; reads device state only, no network.
        viewModelScope.launch {
            while (true) {
                runCatching { container.collector.collect() }.getOrNull()?.let { snap ->
                    _snapshot.value = snap
                    _snapshotHistory.value = (_snapshotHistory.value + snap).takeLast(HISTORY_SIZE)
                }
                delay(5_000)
            }
        }
    }

    fun eventsFor(category: String?): Flow<List<AgentEvent>> =
        if (category == null) container.agentEventDao.recentFlow(200)
        else container.agentEventDao.recentByCategoryFlow(category, 200)

    fun login(serverUrl: String, email: String, password: String) {
        if (_flags.value.loginInProgress) return
        _flags.value = _flags.value.copy(loginInProgress = true, loginError = null)
        viewModelScope.launch {
            val result = container.authRepository.login(serverUrl, email, password)
            _flags.value = _flags.value.copy(
                loginInProgress = false,
                loginError = result.exceptionOrNull()?.message,
            )
            if (result.isSuccess) {
                container.eventLogger.log("user", "info", "Console sign-in", "Signed in on this device.")
            }
        }
    }

    fun enroll() {
        if (_flags.value.enrollInProgress) return
        _flags.value = _flags.value.copy(enrollInProgress = true, enrollError = null)
        viewModelScope.launch {
            val result = container.enrollmentRepository.enroll()
            _flags.value = _flags.value.copy(
                enrollInProgress = false,
                enrollError = result.exceptionOrNull()?.message,
            )
            if (result.isSuccess) {
                container.eventLogger.log("system", "info", "Device enrolled", "Registered with the SentinelX backend.")
                TelemetrySyncWorker.syncNow(appContext)
            }
        }
    }

    /** Enrolment-code path — works for any signed-in role (the code is the authority). */
    fun enrollWithCode(code: String) {
        if (_flags.value.enrollInProgress) return
        _flags.value = _flags.value.copy(enrollInProgress = true, enrollError = null)
        viewModelScope.launch {
            val result = container.enrollmentRepository.enrollWithCode(code)
            _flags.value = _flags.value.copy(
                enrollInProgress = false,
                enrollError = result.exceptionOrNull()?.message,
            )
            if (result.isSuccess) {
                container.eventLogger.log("system", "info", "Device enrolled", "Enrolled with a one-time code.")
                TelemetrySyncWorker.syncNow(appContext)
            }
        }
    }

    /** Collect now: one local sample into the queue, no network. */
    fun collectNow() {
        viewModelScope.launch {
            container.syncEngine.sampleAndQueue()
            container.eventLogger.log("monitoring", "info", "Manual sample collected", "Queued locally for upload.")
        }
    }

    fun syncNow() {
        if (_flags.value.manualSyncInProgress) return
        _flags.value = _flags.value.copy(manualSyncInProgress = true, manualSyncResult = null)
        viewModelScope.launch {
            container.syncEngine.sampleAndQueue()
            val outcome = container.syncEngine.flush()
            val message = when (outcome) {
                is SyncOutcome.Success -> "Uploaded ${outcome.uploaded} sample(s)" +
                    if (outcome.alertsCreated > 0) ", ${outcome.alertsCreated} alert(s) raised" else ""
                is SyncOutcome.Partial -> "Uploaded ${outcome.uploaded}, ${outcome.remaining} still queued: ${outcome.error}"
                is SyncOutcome.Failed -> outcome.error
                is SyncOutcome.Paused -> outcome.reason
                is SyncOutcome.NotEnrolled -> "Enroll this device first"
            }
            _flags.value = _flags.value.copy(manualSyncInProgress = false, manualSyncResult = message)
            // Transient toast-like status; don't let a stale result linger.
            delay(8_000)
            if (_flags.value.manualSyncResult == message) {
                _flags.value = _flags.value.copy(manualSyncResult = null)
            }
        }
    }

    /** Settings diagnostics: round-trip /health and report API/DB status with latency. */
    fun testConnection() {
        if (_flags.value.connectionTestInProgress) return
        _flags.value = _flags.value.copy(connectionTestInProgress = true, connectionTestResult = null)
        viewModelScope.launch {
            val startedAt = System.currentTimeMillis()
            val message = try {
                val health = container.api.health()
                val latency = System.currentTimeMillis() - startedAt
                "API ${health.apiStatus}, database ${health.databaseStatus} · ${latency} ms" +
                    if (health.version.isNotBlank()) " · v${health.version}" else ""
            } catch (t: Throwable) {
                ApiClient.readableError(t)
            }
            _flags.value = _flags.value.copy(connectionTestInProgress = false, connectionTestResult = message)
        }
    }

    fun refreshAlerts() {
        if (_flags.value.alertsRefreshing) return
        _flags.value = _flags.value.copy(alertsRefreshing = true, alertsError = null)
        viewModelScope.launch {
            val token = container.secureStore.deviceToken
            if (token.isNullOrBlank()) {
                _flags.value = _flags.value.copy(alertsRefreshing = false, alertsError = "Enroll this device to see its alerts.")
                return@launch
            }
            try {
                _alerts.value = container.api.myDeviceAlerts("Bearer $token", limit = 50)
                _flags.value = _flags.value.copy(alertsRefreshing = false)
            } catch (t: Throwable) {
                _flags.value = _flags.value.copy(alertsRefreshing = false, alertsError = ApiClient.readableError(t))
            }
        }
    }

    /** Resolve uses the signed-in user's JWT — the device token cannot modify alerts. */
    fun resolveAlert(alertId: String) {
        viewModelScope.launch {
            val jwt = container.secureStore.userJwt
            if (jwt.isNullOrBlank()) {
                _flags.value = _flags.value.copy(alertsError = "Sign in with an engineer+ account to resolve alerts.")
                return@launch
            }
            try {
                val resolved = container.api.resolveAlert("Bearer $jwt", alertId)
                _alerts.value = _alerts.value.map { if (it.id == resolved.id) resolved else it }
                container.eventLogger.log("alerts", "info", "Alert resolved", resolved.message)
            } catch (t: Throwable) {
                _flags.value = _flags.value.copy(alertsError = ApiClient.readableError(t))
            }
        }
    }

    fun runDiagnostics() {
        if (_flags.value.diagnosticsRunning) return
        _flags.value = _flags.value.copy(diagnosticsRunning = true)
        _diagnostics.value = emptyList()
        viewModelScope.launch {
            DiagnosticsRunner(appContext, container).runAll { result ->
                _diagnostics.value = _diagnostics.value + result
            }
            _flags.value = _flags.value.copy(diagnosticsRunning = false)
        }
    }

    fun setLiveMode(enabled: Boolean) {
        if (enabled) LiveMonitorService.start(appContext) else LiveMonitorService.stop(appContext)
    }

    fun setMonitoringMode(mode: String) {
        viewModelScope.launch { container.stateStore.setMonitoringMode(mode) }
    }

    fun setThemeMode(mode: String) {
        viewModelScope.launch { container.stateStore.setThemeMode(mode) }
    }

    fun setWifiOnlyUploads(enabled: Boolean) {
        viewModelScope.launch { container.stateStore.setWifiOnlyUploads(enabled) }
    }

    fun setPauseOnLowBattery(enabled: Boolean) {
        viewModelScope.launch { container.stateStore.setPauseOnLowBattery(enabled) }
    }

    fun setReducedMotion(enabled: Boolean) {
        viewModelScope.launch { container.stateStore.setReducedMotion(enabled) }
    }

    /** Privacy: wipe local telemetry queue and activity timeline. */
    fun deleteLocalData() {
        viewModelScope.launch {
            container.queuedMetricDao.clearAll()
            container.agentEventDao.clearAll()
            container.eventLogger.log("user", "warning", "Local data deleted", "Telemetry queue and activity timeline cleared.")
        }
    }

    fun unenroll() {
        viewModelScope.launch {
            LiveMonitorService.stop(appContext)
            container.enrollmentRepository.unenroll()
            container.queuedMetricDao.clearAll()
            container.eventLogger.log("user", "warning", "Device unenrolled", "Device credential removed; telemetry stopped.")
        }
    }

    fun logout() {
        viewModelScope.launch {
            container.authRepository.logout()
            container.eventLogger.log("user", "info", "Console sign-out")
            _flags.value = UiFlags()
        }
    }

    fun clearLoginError() {
        _flags.value = _flags.value.copy(loginError = null)
    }

    companion object {
        private const val HISTORY_SIZE = 60

        fun factory(container: AppContainer, appContext: Context) =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    AgentViewModel(container, appContext) as T
            }
    }
}
