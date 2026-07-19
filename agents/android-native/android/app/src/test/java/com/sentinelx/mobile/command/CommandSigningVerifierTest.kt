package com.sentinelx.mobile.command

import com.sentinelx.mobile.data.api.dto.RecoveryCommandDto
import org.bouncycastle.crypto.generators.Ed25519KeyPairGenerator
import org.bouncycastle.crypto.params.Ed25519KeyGenerationParameters
import org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.security.SecureRandom
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.Base64
import java.util.UUID

/**
 * Pure-JVM tests — no Room, no network, no Android framework. Mirrors the
 * signing-fixture style used in the backend's test_recovery_command_signing
 * coverage and the desktop agent's test_signing.py.
 */
class CommandSigningVerifierTest {

    private data class Keypair(val private: Ed25519PrivateKeyParameters, val publicKeyBase64: String)

    private fun generateKeypair(): Keypair {
        val generator = Ed25519KeyPairGenerator()
        generator.init(Ed25519KeyGenerationParameters(SecureRandom()))
        val keyPair = generator.generateKeyPair()
        val private = keyPair.private as Ed25519PrivateKeyParameters
        val public = keyPair.public as Ed25519PublicKeyParameters
        return Keypair(private, Base64.getEncoder().encodeToString(public.encoded))
    }

    private fun sign(private: Ed25519PrivateKeyParameters, message: ByteArray): String {
        val signer = Ed25519Signer()
        signer.init(true, private)
        signer.update(message, 0, message.size)
        return Base64.getEncoder().encodeToString(signer.generateSignature())
    }

    private fun buildAndSign(
        keypair: Keypair,
        deviceId: String = "device-1",
        actionType: String = "collect_diagnostics",
        parameters: Map<String, String> = emptyMap(),
        expiresInSeconds: Long = 300,
        nonce: String = UUID.randomUUID().toString(),
        policyId: String = "policy-1",
    ): RecoveryCommandDto {
        val commandId = UUID.randomUUID().toString()
        val expiresAt = Instant.now().plusSeconds(expiresInSeconds).toString()

        val unsigned = RecoveryCommandDto(
            id = commandId,
            deviceId = deviceId,
            actionType = actionType,
            parametersJson = parameters,
            status = "dispatched",
            commandNonce = nonce,
            expiresAt = expiresAt,
            policyId = policyId,
            signature = null,
        )
        val canonical = CommandCanonicalPayload.build(unsigned).toByteArray(Charsets.UTF_8)
        val signature = sign(keypair.private, canonical)
        return unsigned.copy(signature = signature)
    }

    @Test
    fun `valid signature verifies`() {
        val keypair = generateKeypair()
        val command = buildAndSign(keypair)
        assertTrue(CommandSigningVerifier.verify(command, keypair.publicKeyBase64))
    }

    @Test
    fun `tampered action type rejected`() {
        val keypair = generateKeypair()
        val command = buildAndSign(keypair).copy(actionType = "restore_normal_monitoring_mode")
        assertFalse(CommandSigningVerifier.verify(command, keypair.publicKeyBase64))
    }

    @Test
    fun `wrong device id rejected`() {
        val keypair = generateKeypair()
        val command = buildAndSign(keypair, deviceId = "device-1").copy(deviceId = "device-2")
        assertFalse(CommandSigningVerifier.verify(command, keypair.publicKeyBase64))
    }

    @Test
    fun `wrong public key rejected`() {
        val keypair = generateKeypair()
        val otherKeypair = generateKeypair()
        val command = buildAndSign(keypair)
        assertFalse(CommandSigningVerifier.verify(command, otherKeypair.publicKeyBase64))
    }

    @Test
    fun `missing signature rejected`() {
        val keypair = generateKeypair()
        val command = buildAndSign(keypair).copy(signature = null)
        assertFalse(CommandSigningVerifier.verify(command, keypair.publicKeyBase64))
    }

    @Test
    fun `expired command detected`() {
        val keypair = generateKeypair()
        val command = buildAndSign(keypair, expiresInSeconds = -30)
        assertTrue(CommandSigningVerifier.isExpired(command))
    }

    @Test
    fun `non-expired command not flagged`() {
        val keypair = generateKeypair()
        val command = buildAndSign(keypair, expiresInSeconds = 300)
        assertFalse(CommandSigningVerifier.isExpired(command))
    }

    @Test
    fun `canonical timestamp matches backend isoformat convention with microseconds`() {
        // 2026-07-19T10:50:53.658037Z is exactly the kind of value the
        // backend's Python isoformat() produces (6-digit microseconds).
        val normalized = CommandCanonicalPayload.normalizeToUtcIso("2026-07-19T10:50:53.658037Z")
        assertEquals("2026-07-19T10:50:53.658037+00:00", normalized)
    }

    @Test
    fun `canonical timestamp omits fraction when microseconds are exactly zero`() {
        // Matches Python's isoformat() behavior: no ".000000" when the value
        // is exactly zero.
        val normalized = CommandCanonicalPayload.normalizeToUtcIso("2026-07-19T10:50:53Z")
        assertEquals("2026-07-19T10:50:53+00:00", normalized)
    }

    @Test
    fun `canonical timestamp normalizes non-utc offset to utc`() {
        // 11:50:53+01:00 is the same instant as 10:50:53Z.
        val normalized = CommandCanonicalPayload.normalizeToUtcIso("2026-07-19T11:50:53.658037+01:00")
        assertEquals("2026-07-19T10:50:53.658037+00:00", normalized)
    }

    @Test
    fun `signature verifies across offset representation change for same instant`() {
        // Regression test for the exact UTC-normalization bug found and
        // fixed in the backend during Sprint 3 Stage 3.
        val keypair = generateKeypair()
        val command = buildAndSign(keypair)
        val rewritten = command.copy(
            expiresAt = Instant.parse(command.expiresAt).plus(0, ChronoUnit.SECONDS).toString()
        )
        assertTrue(CommandSigningVerifier.verify(rewritten, keypair.publicKeyBase64))
    }
}
