package com.sentinelx.mobile.data.repo

import com.sentinelx.mobile.BuildConfig
import com.sentinelx.mobile.data.api.ApiClient
import com.sentinelx.mobile.data.api.SentinelXApi
import com.sentinelx.mobile.data.api.dto.DeviceCredentialCreateRequest
import com.sentinelx.mobile.data.api.dto.DeviceEnrollRequest
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
     * Preferred path: exchange a single-use enrolment code minted by an org
     * admin for a device identity + token. No admin login on the phone needed.
     */
    suspend fun enrollWithCode(code: String): Result<Unit> {
        val trimmed = code.trim()
        if (trimmed.isBlank()) {
            return Result.failure(IllegalArgumentException("Enter an enrolment code."))
        }
        return try {
            val hostname = collector.stableHostname()
            val response = api.enrollDevice(
                DeviceEnrollRequest(
                    enrollmentCode = trimmed,
                    hostname = hostname,
                    displayName = collector.displayName(),
                    osName = collector.osName(),
                    agentVersion = BuildConfig.VERSION_NAME,
                )
            )
            secureStore.deviceToken = response.deviceToken
            stateStore.saveDeviceIdentity(response.device.id, hostname, response.credentialId)
            Result.success(Unit)
        } catch (t: Throwable) {
            Result.failure(RuntimeException(ApiClient.readableError(t), t))
        }
    }

    /**
     * Admin-JWT self-enrolment (kept for the console workflow). Registers this
     * phone and mints its token; the previously issued credential is revoked
     * so re-enrolment can no longer accumulate live tokens.
     */
    suspend fun enroll(): Result<Unit> {
        val state = stateStore.current()
        val jwt = secureStore.userJwt
            ?: return Result.failure(IllegalStateException("Sign in first."))

        if (!state.canEnroll) {
            return Result.failure(
                IllegalStateException(
                    "Enrollment needs an admin or owner account (current role: ${state.userRole.ifBlank { "unknown" }}). " +
                        "Sign in with e.g. ops@technova.io, or use an enrolment code instead."
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
                auth,
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

            // Kill the token this phone held before; only the new one stays valid.
            val previousCredentialId = state.credentialId
            if (previousCredentialId.isNotBlank() && previousCredentialId != credential.id) {
                try {
                    api.revokeCredential(auth, previousCredentialId)
                } catch (_: Exception) {
                    // Best-effort: an admin can still revoke it from the console.
                }
            }

            secureStore.deviceToken = credential.token
            stateStore.saveDeviceIdentity(device.id, hostname, credential.id)
            Result.success(Unit)
        } catch (t: Throwable) {
            Result.failure(RuntimeException(ApiClient.readableError(t), t))
        }
    }

    /**
     * Revokes the backend credential first, then forgets local state — a lost
     * or copied token no longer outlives the unenrolment.
     */
    suspend fun unenroll() {
        val token = secureStore.deviceToken
        if (!token.isNullOrBlank()) {
            try {
                api.revokeSelfCredential("Bearer $token")
            } catch (_: Exception) {
                // Offline unenrol still clears locally; the credential can be
                // revoked from the console afterwards.
            }
        }
        secureStore.deviceToken = null
        stateStore.clearDeviceIdentity()
    }
}
