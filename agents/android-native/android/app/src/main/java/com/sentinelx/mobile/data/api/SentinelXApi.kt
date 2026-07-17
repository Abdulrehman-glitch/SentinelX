package com.sentinelx.mobile.data.api

import com.sentinelx.mobile.data.api.dto.AlertDto
import com.sentinelx.mobile.data.api.dto.DeviceCredentialCreateRequest
import com.sentinelx.mobile.data.api.dto.DeviceCredentialCreateResponse
import com.sentinelx.mobile.data.api.dto.DeviceDto
import com.sentinelx.mobile.data.api.dto.DeviceEnrollRequest
import com.sentinelx.mobile.data.api.dto.DeviceEnrollResponse
import com.sentinelx.mobile.data.api.dto.DeviceRegisterRequest
import com.sentinelx.mobile.data.api.dto.HealthResponse
import com.sentinelx.mobile.data.api.dto.HeartbeatDto
import com.sentinelx.mobile.data.api.dto.HeartbeatRequest
import com.sentinelx.mobile.data.api.dto.LoginRequest
import com.sentinelx.mobile.data.api.dto.LoginResponse
import com.sentinelx.mobile.data.api.dto.MetricBatchRequest
import com.sentinelx.mobile.data.api.dto.MetricBatchResponse
import com.sentinelx.mobile.data.api.dto.MetricIngestResponse
import com.sentinelx.mobile.data.api.dto.MetricRequest
import com.sentinelx.mobile.data.api.dto.OrganizationDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface SentinelXApi {

    @GET("api/v1/health")
    suspend fun health(): HealthResponse

    @POST("api/v1/auth/login")
    suspend fun login(@Body body: LoginRequest): LoginResponse

    @GET("api/v1/organizations/me")
    suspend fun myOrganization(@Header("Authorization") auth: String): OrganizationDto

    // Admin-JWT gated on the backend now; anonymous registration was removed.
    @POST("api/v1/devices/register")
    suspend fun registerDevice(
        @Header("Authorization") auth: String,
        @Body body: DeviceRegisterRequest,
    ): DeviceDto

    /** Exchanges a single-use enrolment code for a device + device token. */
    @POST("api/v1/devices/enroll")
    suspend fun enrollDevice(@Body body: DeviceEnrollRequest): DeviceEnrollResponse

    /** Revokes the presenting device credential (used on unenrol). */
    @POST("api/v1/device-credentials/revoke-self")
    suspend fun revokeSelfCredential(@Header("Authorization") auth: String)

    @PATCH("api/v1/device-credentials/{credentialId}/revoke")
    suspend fun revokeCredential(
        @Header("Authorization") auth: String,
        @Path("credentialId") credentialId: String,
    )

    @POST("api/v1/device-credentials")
    suspend fun createDeviceCredential(
        @Header("Authorization") auth: String,
        @Body body: DeviceCredentialCreateRequest,
    ): DeviceCredentialCreateResponse

    @POST("api/v1/heartbeats")
    suspend fun sendHeartbeat(
        @Header("Authorization") auth: String,
        @Body body: HeartbeatRequest,
    ): HeartbeatDto

    @POST("api/v1/metrics")
    suspend fun ingestMetric(
        @Header("Authorization") auth: String,
        @Body body: MetricRequest,
    ): MetricIngestResponse

    @POST("api/v1/metrics/batch")
    suspend fun ingestMetricBatch(
        @Header("Authorization") auth: String,
        @Body body: MetricBatchRequest,
    ): MetricBatchResponse

    @GET("api/v1/alerts/device/me")
    suspend fun myDeviceAlerts(
        @Header("Authorization") auth: String,
        @Query("unresolved_only") unresolvedOnly: Boolean = false,
        @Query("limit") limit: Int = 50,
    ): List<AlertDto>

    @PATCH("api/v1/alerts/{alertId}/resolve")
    suspend fun resolveAlert(
        @Header("Authorization") auth: String,
        @Path("alertId") alertId: String,
    ): AlertDto
}
