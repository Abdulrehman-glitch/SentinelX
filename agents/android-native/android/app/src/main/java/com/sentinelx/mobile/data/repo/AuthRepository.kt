package com.sentinelx.mobile.data.repo

import com.sentinelx.mobile.data.api.ApiClient
import com.sentinelx.mobile.data.api.HostSelectionInterceptor
import com.sentinelx.mobile.data.api.SentinelXApi
import com.sentinelx.mobile.data.api.dto.LoginRequest
import com.sentinelx.mobile.data.prefs.AgentStateStore
import com.sentinelx.mobile.data.prefs.SecureStore

class AuthRepository(
    private val api: SentinelXApi,
    private val stateStore: AgentStateStore,
    private val secureStore: SecureStore,
) {

    /**
     * Logs in and persists base URL + session atomically: the candidate URL is
     * staged for the interceptor, but a failed login rolls it back so the app
     * never ends up pointing at a new server with the old JWT/user state.
     */
    suspend fun login(rawBaseUrl: String, email: String, password: String): Result<Unit> {
        val normalized = HostSelectionInterceptor.normalize(rawBaseUrl)
            ?: return Result.failure(
                IllegalArgumentException("Enter a valid server URL (HTTPS required in release builds).")
            )

        val previous = stateStore.current()
        stateStore.saveBaseUrl(normalized)

        return try {
            val response = api.login(LoginRequest(email = email.trim(), password = password))
            secureStore.userJwt = response.accessToken
            stateStore.saveLogin(normalized, response.user.email, response.user.fullName, response.user.role)

            // Org slug is needed later for device registration; fetch it while the JWT is fresh.
            if (response.user.organizationId != null) {
                try {
                    val org = api.myOrganization("Bearer ${response.accessToken}")
                    stateStore.saveOrganization(org.slug, org.name)
                } catch (_: Exception) {
                    // Non-fatal: enrollment will retry the lookup.
                }
            }
            Result.success(Unit)
        } catch (t: Throwable) {
            if (previous.baseUrl.isNotBlank()) {
                stateStore.saveBaseUrl(previous.baseUrl)
            }
            Result.failure(RuntimeException(ApiClient.readableError(t), t))
        }
    }

    /** Ends the console session. Device enrollment and telemetry keep working on the device token. */
    suspend fun logout() {
        secureStore.clearUserJwt()
        stateStore.clearSession()
    }
}
