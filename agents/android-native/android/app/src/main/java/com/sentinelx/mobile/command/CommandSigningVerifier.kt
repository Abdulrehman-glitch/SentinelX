package com.sentinelx.mobile.command

import com.sentinelx.mobile.data.api.dto.RecoveryCommandDto
import java.util.Base64
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import java.time.OffsetDateTime
import java.time.ZoneOffset

/**
 * Builds the exact canonical string backend/app/services/recovery_command_service.py
 * ::build_canonical_payload signs, and verifies it with BouncyCastle's
 * lightweight Ed25519 API (no JCE provider registration needed — works down
 * to minSdk 26, unlike java.security's native Ed25519 support which needs
 * API 33+).
 */
object CommandCanonicalPayload {

    fun build(command: RecoveryCommandDto): String {
        val canonicalParams = canonicalJsonObject(command.parametersJson)
        val expiresAtUtc = normalizeToUtcIso(command.expiresAt)
        return listOf(
            command.id,
            command.deviceId,
            command.actionType,
            canonicalParams,
            command.commandNonce ?: "",
            expiresAtUtc,
            expiresAtUtc,
            command.policyId ?: "",
        ).joinToString("\n")
    }

    private fun canonicalJsonObject(parameters: Map<String, String>): String {
        if (parameters.isEmpty()) return "{}"
        val sorted = parameters.toSortedMap()
        val body = sorted.entries.joinToString(",") { (key, value) -> "${jsonString(key)}:${jsonString(value)}" }
        return "{$body}"
    }

    private fun jsonString(value: String): String {
        val escaped = value
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        return "\"$escaped\""
    }

    /**
     * Parses any valid ISO-8601 offset (trailing 'Z' or an explicit offset)
     * and re-renders it in UTC exactly the way Python's
     * datetime.astimezone(timezone.utc).isoformat() does: no fractional part
     * when microseconds are exactly zero, otherwise exactly 6 digits, always
     * a '+00:00' suffix. This must stay byte-identical with the backend and
     * the desktop agent's signing.py — verified by CommandSigningVerifierTest.
     */
    fun normalizeToUtcIso(raw: String?): String {
        if (raw.isNullOrEmpty()) return ""
        val parsed = OffsetDateTime.parse(raw).withOffsetSameInstant(ZoneOffset.UTC)
        val micros = parsed.nano / 1000
        val base = "%04d-%02d-%02dT%02d:%02d:%02d".format(
            parsed.year, parsed.monthValue, parsed.dayOfMonth, parsed.hour, parsed.minute, parsed.second
        )
        return if (micros == 0) "$base+00:00" else "$base.${"%06d".format(micros)}+00:00"
    }
}

object CommandSigningVerifier {

    fun verify(command: RecoveryCommandDto, publicKeyBase64: String): Boolean {
        val signatureBase64 = command.signature ?: return false
        return try {
            val publicKeyBytes = Base64.getDecoder().decode(publicKeyBase64)
            val signatureBytes = Base64.getDecoder().decode(signatureBase64)
            val canonical = CommandCanonicalPayload.build(command).toByteArray(Charsets.UTF_8)

            val publicKeyParams = Ed25519PublicKeyParameters(publicKeyBytes, 0)
            val signer = Ed25519Signer()
            signer.init(false, publicKeyParams)
            signer.update(canonical, 0, canonical.size)
            signer.verifySignature(signatureBytes)
        } catch (_: Exception) {
            // Any malformed input (bad base64, wrong key length, corrupt
            // signature) is a verification failure, never a crash.
            false
        }
    }

    fun isExpired(command: RecoveryCommandDto, nowEpochMs: Long = System.currentTimeMillis()): Boolean {
        val expiresAtRaw = command.expiresAt ?: return false
        if (expiresAtRaw.isEmpty()) return false
        val expiresAt = OffsetDateTime.parse(expiresAtRaw).toInstant().toEpochMilli()
        return nowEpochMs > expiresAt
    }
}
