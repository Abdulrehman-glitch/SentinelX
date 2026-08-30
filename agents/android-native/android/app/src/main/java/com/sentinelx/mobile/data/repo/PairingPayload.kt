package com.sentinelx.mobile.data.repo

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * The payload inside a SentinelX console pairing QR code:
 * {"v":1,"t":"sentinelx-pair","url":"http://192.168.1.42:8000","code":"sxe_..."}
 *
 * It carries a short-lived single-use enrolment code, never a device token —
 * the phone exchanges it for its real credential over the network.
 */
@Serializable
data class PairingPayload(
    val v: Int = 1,
    val t: String = "",
    val url: String = "",
    val code: String = "",
) {
    companion object {
        private val json = Json { ignoreUnknownKeys = true }

        /** Accepts the console QR JSON or a bare sxe_ pairing code typed by hand. */
        fun parse(raw: String): PairingPayload? {
            val trimmed = raw.trim()
            if (trimmed.startsWith("sxe_")) return PairingPayload(code = trimmed)
            if (!trimmed.startsWith("{")) return null
            return try {
                val parsed = json.decodeFromString(serializer(), trimmed)
                if (parsed.t == "sentinelx-pair" && parsed.code.isNotBlank()) parsed else null
            } catch (_: Exception) {
                null
            }
        }
    }
}
