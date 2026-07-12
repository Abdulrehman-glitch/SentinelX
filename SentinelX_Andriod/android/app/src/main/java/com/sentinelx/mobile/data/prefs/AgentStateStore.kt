package com.sentinelx.mobile.data.prefs

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "sentinelx_agent_state")

data class AgentState(
    val baseUrl: String = "",
    val userEmail: String = "",
    val userFullName: String = "",
    val userRole: String = "",
    val orgSlug: String = "",
    val orgName: String = "",
    val deviceId: String = "",
    val deviceHostname: String = "",
    val liveIntervalSeconds: Int = 30,
    val liveModeActive: Boolean = false,
    val lastSyncAtEpochMs: Long = 0L,
    val lastSyncError: String = "",
    val lastAlertsCreated: Int = 0,
) {
    val isLoggedIn: Boolean get() = userEmail.isNotBlank()
    val isEnrolled: Boolean get() = deviceId.isNotBlank()
    val canEnroll: Boolean get() = userRole in setOf("admin", "owner", "platform_admin")
}

class AgentStateStore(private val context: Context) {

    val state: Flow<AgentState> = context.dataStore.data.map { p ->
        AgentState(
            baseUrl = p[BASE_URL] ?: "",
            userEmail = p[USER_EMAIL] ?: "",
            userFullName = p[USER_FULL_NAME] ?: "",
            userRole = p[USER_ROLE] ?: "",
            orgSlug = p[ORG_SLUG] ?: "",
            orgName = p[ORG_NAME] ?: "",
            deviceId = p[DEVICE_ID] ?: "",
            deviceHostname = p[DEVICE_HOSTNAME] ?: "",
            liveIntervalSeconds = p[LIVE_INTERVAL_SECONDS] ?: 30,
            liveModeActive = p[LIVE_MODE_ACTIVE] ?: false,
            lastSyncAtEpochMs = p[LAST_SYNC_AT] ?: 0L,
            lastSyncError = p[LAST_SYNC_ERROR] ?: "",
            lastAlertsCreated = p[LAST_ALERTS_CREATED] ?: 0,
        )
    }

    suspend fun current(): AgentState = state.first()

    suspend fun saveLogin(baseUrl: String, email: String, fullName: String, role: String) {
        context.dataStore.edit { p ->
            p[BASE_URL] = baseUrl
            p[USER_EMAIL] = email
            p[USER_FULL_NAME] = fullName
            p[USER_ROLE] = role
        }
    }

    suspend fun saveOrganization(slug: String, name: String) {
        context.dataStore.edit { p ->
            p[ORG_SLUG] = slug
            p[ORG_NAME] = name
        }
    }

    suspend fun saveDeviceIdentity(deviceId: String, hostname: String) {
        context.dataStore.edit { p ->
            p[DEVICE_ID] = deviceId
            p[DEVICE_HOSTNAME] = hostname
        }
    }

    suspend fun clearDeviceIdentity() {
        context.dataStore.edit { p ->
            p.remove(DEVICE_ID)
            p.remove(DEVICE_HOSTNAME)
        }
    }

    suspend fun setLiveInterval(seconds: Int) {
        context.dataStore.edit { p -> p[LIVE_INTERVAL_SECONDS] = seconds }
    }

    suspend fun setLiveModeActive(active: Boolean) {
        context.dataStore.edit { p -> p[LIVE_MODE_ACTIVE] = active }
    }

    suspend fun recordSyncResult(successAtEpochMs: Long?, error: String?, alertsCreated: Int = 0) {
        context.dataStore.edit { p ->
            if (successAtEpochMs != null) p[LAST_SYNC_AT] = successAtEpochMs
            p[LAST_SYNC_ERROR] = error ?: ""
            p[LAST_ALERTS_CREATED] = alertsCreated
        }
    }

    suspend fun clearSession() {
        context.dataStore.edit { p ->
            p.remove(USER_EMAIL)
            p.remove(USER_FULL_NAME)
            p.remove(USER_ROLE)
        }
    }

    private companion object {
        val BASE_URL = stringPreferencesKey("base_url")
        val USER_EMAIL = stringPreferencesKey("user_email")
        val USER_FULL_NAME = stringPreferencesKey("user_full_name")
        val USER_ROLE = stringPreferencesKey("user_role")
        val ORG_SLUG = stringPreferencesKey("org_slug")
        val ORG_NAME = stringPreferencesKey("org_name")
        val DEVICE_ID = stringPreferencesKey("device_id")
        val DEVICE_HOSTNAME = stringPreferencesKey("device_hostname")
        val LIVE_INTERVAL_SECONDS = intPreferencesKey("live_interval_seconds")
        val LIVE_MODE_ACTIVE = booleanPreferencesKey("live_mode_active")
        val LAST_SYNC_AT = longPreferencesKey("last_sync_at")
        val LAST_SYNC_ERROR = stringPreferencesKey("last_sync_error")
        val LAST_ALERTS_CREATED = intPreferencesKey("last_alerts_created")
    }
}
