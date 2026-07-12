package com.sentinelx.mobile.data.api

import com.sentinelx.mobile.data.api.dto.DeviceCredentialCreateRequest
import com.sentinelx.mobile.data.api.dto.DeviceCredentialCreateResponse
import com.sentinelx.mobile.data.api.dto.DeviceDto
import com.sentinelx.mobile.data.api.dto.DeviceRegisterRequest
import com.sentinelx.mobile.data.api.dto.HealthResponse
import com.sentinelx.mobile.data.api.dto.HeartbeatDto
import com.sentinelx.mobile.data.api.dto.HeartbeatRequest
import com.sentinelx.mobile.data.api.dto.LoginRequest
import com.sentinelx.mobile.data.api.dto.LoginResponse
import com.sentinelx.mobile.data.api.dto.MetricIngestResponse
import com.sentinelx.mobile.data.api.dto.MetricRequest
import com.sentinelx.mobile.data.api.dto.OrganizationDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

interface SentinelXApi {

    @GET("api/v1/health")
    suspend fun health(): HealthResponse

    @POST("api/v1/auth/login")
    suspend fun login(@Body body: LoginRequest): LoginResponse

    @GET("api/v1/organizations/me")
    suspend fun myOrganization(@Header("Authorization") auth: String): OrganizationDto

    @POST("api/v1/devices/register")
    suspend fun registerDevice(@Body body: DeviceRegisterRequest): DeviceDto

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
}
