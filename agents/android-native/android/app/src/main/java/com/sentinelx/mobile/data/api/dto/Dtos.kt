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
data class MetricSampleDto(
    /** Client-generated UUID; the backend deduplicates retried uploads on it. */
    @SerialName("event_id") val eventId: String? = null,
    /** Frequency-based estimate; null when unreadable — never a fabricated 0%. */
    @SerialName("cpu_percent") val cpuPercent: Double? = null,
    @SerialName("memory_percent") val memoryPercent: Double,
    @SerialName("disk_percent") val diskPercent: Double,
    @SerialName("battery_percent") val batteryPercent: Double? = null,
    @SerialName("battery_charging") val batteryCharging: Boolean? = null,
    @SerialName("battery_temperature_c") val batteryTemperatureC: Double? = null,
    @SerialName("thermal_status") val thermalStatus: String? = null,
    @SerialName("network_transport") val networkTransport: String? = null,
    @SerialName("network_validated") val networkValidated: Boolean? = null,
    @SerialName("network_metered") val networkMetered: Boolean? = null,
    @SerialName("latency_ms") val latencyMs: Double? = null,
    /** ISO-8601 UTC capture time so an offline flush lands as real history. */
    @SerialName("recorded_at") val recordedAt: String? = null,
)

@Serializable
data class MetricBatchRequest(
    @SerialName("device_id") val deviceId: String,
    val samples: List<MetricSampleDto>,
)

@Serializable
data class MetricBatchResponse(
    val stored: Int,
    val duplicates: Int = 0,
    @SerialName("alerts_created") val alertsCreated: Int = 0,
)


@Serializable
data class DeviceEnrollRequest(
    @SerialName("enrollment_code") val enrollmentCode: String,
    val hostname: String,
    @SerialName("display_name") val displayName: String,
    @SerialName("os_name") val osName: String,
    @SerialName("device_type") val deviceType: String = "mobile",
    @SerialName("agent_type") val agentType: String = "android_mobile_agent",
    @SerialName("agent_version") val agentVersion: String,
)


@Serializable
data class DeviceEnrollResponse(
    val device: DeviceDto,
    @SerialName("credential_id") val credentialId: String,
    /** Shown once by the backend; stored straight into EncryptedSharedPreferences. */
    @SerialName("device_token") val deviceToken: String,
)

@Serializable
data class AlertDto(
    val id: String,
    @SerialName("device_id") val deviceId: String,
    @SerialName("alert_type") val alertType: String,
    val severity: String,
    val message: String,
    val resolved: Boolean = false,
    @SerialName("created_at") val createdAt: String,
    @SerialName("resolved_at") val resolvedAt: String? = null,
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

// ── Safe Recovery Orchestration (Sprint 3) ──────────────────────────────────
// parameters_json/result_data/post_action_snapshot are constrained to flat
// String-valued maps here: every allowlisted Android action in this sprint
// takes no parameters, and diagnostic values are serialized as strings —
// the backend's JSONB column accepts this fine. A genuinely nested/typed
// parameters_json would need a fuller canonical-JSON implementation to stay
// byte-identical with the backend's Python signer (see CommandCanonicalPayload).

@Serializable
data class RecoveryCommandDto(
    val id: String,
    @SerialName("device_id") val deviceId: String,
    @SerialName("action_type") val actionType: String,
    @SerialName("parameters_json") val parametersJson: Map<String, String> = emptyMap(),
    val status: String,
    @SerialName("command_nonce") val commandNonce: String? = null,
    @SerialName("payload_hash") val payloadHash: String? = null,
    val signature: String? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
    @SerialName("policy_id") val policyId: String? = null,
)

@Serializable
data class RecoveryCommandCapabilityDto(
    @SerialName("action_type") val actionType: String,
    @SerialName("action_version") val actionVersion: String = "1",
    @SerialName("local_risk_level") val localRiskLevel: String,
)

@Serializable
data class ReportCapabilitiesRequest(
    @SerialName("agent_type") val agentType: String,
    @SerialName("agent_version") val agentVersion: String,
    val capabilities: List<RecoveryCommandCapabilityDto>,
)

@Serializable
data class CompleteCommandRequest(
    @SerialName("result_code") val resultCode: String,
    @SerialName("result_message") val resultMessage: String? = null,
    @SerialName("result_data") val resultData: Map<String, String>? = null,
    @SerialName("post_action_snapshot") val postActionSnapshot: Map<String, String>? = null,
)

@Serializable
data class RejectCommandRequest(
    val reason: String,
)

@Serializable
data class PublicKeyResponse(
    @SerialName("public_key") val publicKey: String,
)
