package com.sentinelx.mobile.ui

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.sentinelx.mobile.core.AppContainer
import com.sentinelx.mobile.data.api.ApiClient
import com.sentinelx.mobile.data.prefs.AgentState
import com.sentinelx.mobile.sync.LiveMonitorService
import com.sentinelx.mobile.sync.SyncOutcome
import com.sentinelx.mobile.sync.TelemetrySyncWorker
import com.sentinelx.mobile.telemetry.TelemetrySnapshot
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
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
)

/**
 * One ViewModel drives all three screens; the app is small enough that
 * splitting it would only add plumbing.
 */
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

    init {
        // Local dashboard refresh; reads device state only, no network.
        viewModelScope.launch {
            while (true) {
                _snapshot.value = runCatching { container.collector.collect() }.getOrNull()
                delay(5_000)
            }
        }
    }

    fun login(serverUrl: String, email: String, password: String) {
        if (_flags.value.loginInProgress) return
        _flags.value = _flags.value.copy(loginInProgress = true, loginError = null)
        viewModelScope.launch {
            val result = container.authRepository.login(serverUrl, email, password)
            _flags.value = _flags.value.copy(
                loginInProgress = false,
                loginError = result.exceptionOrNull()?.message,
            )
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
                TelemetrySyncWorker.syncNow(appContext)
            }
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

    fun setLiveMode(enabled: Boolean) {
        if (enabled) LiveMonitorService.start(appContext) else LiveMonitorService.stop(appContext)
    }

    fun setLiveInterval(seconds: Int) {
        viewModelScope.launch { container.stateStore.setLiveInterval(seconds) }
    }

    fun unenroll() {
        viewModelScope.launch {
            LiveMonitorService.stop(appContext)
            container.enrollmentRepository.unenroll()
            container.queuedMetricDao.clearAll()
        }
    }

    fun logout() {
        viewModelScope.launch {
            container.authRepository.logout()
            _flags.value = UiFlags()
        }
    }

    fun clearLoginError() {
        _flags.value = _flags.value.copy(loginError = null)
    }

    companion object {
        fun factory(container: AppContainer, appContext: Context) =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    AgentViewModel(container, appContext) as T
            }
    }
}
