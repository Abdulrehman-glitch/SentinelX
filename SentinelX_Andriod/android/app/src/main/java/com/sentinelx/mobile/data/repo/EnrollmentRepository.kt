package com.sentinelx.mobile.data.repo

import com.sentinelx.mobile.BuildConfig
import com.sentinelx.mobile.data.api.ApiClient
import com.sentinelx.mobile.data.api.SentinelXApi
import com.sentinelx.mobile.data.api.dto.DeviceCredentialCreateRequest
import com.sentinelx.mobile.data.api.dto.DeviceRegisterRequest
import com.sentinelx.mobile.data.prefs.AgentStateStore
import com.sentinelx.mobile.data.prefs.SecureStore
import com.sentinelx.mobile.telemetry.DeviceTelemetryCollector

class EnrollmentRepository(
    private val api: SentinelXApi,
    private val stateStore: AgentStateStore,
    private val secureStore: SecureStore,
    private val collector: DeviceTelemetryCollector,
) {

    /**
     * Registers this phone as a SentinelX device and mints its device token.
     * Requires an admin/owner/platform_admin JWT because /device-credentials is
     * role-gated on the backend. Idempotent: re-running refreshes the same
     * device row (hostname is stable) and issues a fresh credential.
     */
    suspend fun enroll(): Result<Unit> {
        val state = stateStore.current()
        val jwt = secureStore.userJwt
            ?: return Result.failure(IllegalStateException("Sign in first."))

        if (!state.canEnroll) {
            return Result.failure(
                IllegalStateException(
                    "Enrollment needs an admin or owner account (current role: ${state.userRole.ifBlank { "unknown" }}). " +
                        "Sign in with e.g. ops@technova.io."
                )
            )
        }

        return try {
            val auth = "Bearer $jwt"

            var orgSlug = state.orgSlug
            if (orgSlug.isBlank()) {
                val org = api.myOrganization(auth)
                stateStore.saveOrganization(org.slug, org.name)
                orgSlug = org.slug
            }

            val hostname = collector.stableHostname()
            val device = api.registerDevice(
                DeviceRegisterRequest(
                    hostname = hostname,
                    displayName = collector.displayName(),
                    osName = collector.osName(),
                    organizationSlug = orgSlug,
                    agentVersion = BuildConfig.VERSION_NAME,
                )
            )

            val credential = api.createDeviceCredential(
                auth,
                DeviceCredentialCreateRequest(deviceId = device.id, name = "Android agent – $hostname"),
            )

            secureStore.deviceToken = credential.token
            stateStore.saveDeviceIdentity(device.id, hostname)
            Result.success(Unit)
        } catch (t: Throwable) {
            Result.failure(RuntimeException(ApiClient.readableError(t), t))
        }
    }

    /** Forgets the local device identity and token (the backend Device row is kept). */
    suspend fun unenroll() {
        secureStore.deviceToken = null
        stateStore.clearDeviceIdentity()
    }
}
