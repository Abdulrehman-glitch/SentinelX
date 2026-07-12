package com.sentinelx.mobile.data.api.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class LoginRequest(
    val email: String,
    val password: String,
)

@Serializable
data class UserDto(
    val id: String,
    val email: String,
    @SerialName("full_name") val fullName: String,
    val role: String,
    @SerialName("is_active") val isActive: Boolean = true,
    @SerialName("organization_id") val organizationId: String? = null,
)

@Serializable
data class LoginResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("token_type") val tokenType: String = "bearer",
    val user: UserDto,
)

@Serializable
data class OrganizationDto(
    val id: String,
    val name: String,
    val slug: String,
)

@Serializable
data class DeviceRegisterRequest(
    val hostname: String,
    @SerialName("display_name") val displayName: String,
    @SerialName("ip_address") val ipAddress: String? = null,
    @SerialName("os_name") val osName: String,
    @SerialName("organization_slug") val organizationSlug: String,
    @SerialName("device_type") val deviceType: String = "mobile",
    @SerialName("agent_type") val agentType: String = "android_mobile_agent",
    @SerialName("agent_version") val agentVersion: String,
)

@Serializable
data class DeviceDto(
    val id: String,
    val hostname: String,
    @SerialName("display_name") val displayName: String? = null,
    @SerialName("organization_id") val organizationId: String? = null,
    val status: String = "online",
)

@Serializable
data class DeviceCredentialCreateRequest(
    @SerialName("device_id") val deviceId: String,
    val name: String,
)

@Serializable
data class DeviceCredentialCreateResponse(
    val id: String,
    val token: String,
    @SerialName("token_preview") val tokenPreview: String,
)

@Serializable
data class HeartbeatRequest(
    @SerialName("device_id") val deviceId: String,
    val status: String = "online",
    val message: String? = null,
)

@Serializable
data class HeartbeatDto(
    val id: String,
    val status: String,
)

@Serializable
data class MetricRequest(
    @SerialName("device_id") val deviceId: String,
    @SerialName("cpu_percent") val cpuPercent: Double,
    @SerialName("memory_percent") val memoryPercent: Double,
    @SerialName("disk_percent") val diskPercent: Double,
)

@Serializable
data class MetricDto(
    val id: String,
    @SerialName("recorded_at") val recordedAt: String,
)

@Serializable
data class MetricIngestResponse(
    val metric: MetricDto,
    @SerialName("alerts_created") val alertsCreated: Int = 0,
)

@Serializable
data class HealthResponse(
    @SerialName("api_status") val apiStatus: String = "unknown",
    @SerialName("database_status") val databaseStatus: String = "unknown",
    val version: String = "",
)

@Serializable
data class ApiErrorBody(
    val detail: String? = null,
)
