package com.sentinelx.mobile.command

import com.sentinelx.mobile.data.api.SentinelXApi
import com.sentinelx.mobile.data.api.dto.CompleteCommandRequest
import com.sentinelx.mobile.data.api.dto.RecoveryCommandCapabilityDto
import com.sentinelx.mobile.data.api.dto.RecoveryCommandDto
import com.sentinelx.mobile.data.api.dto.RejectCommandRequest
import com.sentinelx.mobile.data.api.dto.ReportCapabilitiesRequest
import com.sentinelx.mobile.data.db.CommandRecord
import com.sentinelx.mobile.data.db.CommandRecordDao
import com.sentinelx.mobile.data.prefs.SecureStore

private const val AGENT_TYPE = "android_mobile_agent"
private const val AGENT_VERSION = "3.0.0"

/**
 * Polls for the single active signed command for this device, verifies it,
 * executes the allowlisted action, and reports the result back — every step
 * persisted to Room (CommandRecordDao) before the network call that reports
 * it, so a process death mid-command resumes from durable state rather than
 * re-executing or silently losing the result. Mirrors the desktop agent's
 * sentinelx_agent/commands.py. The public key is fetched fresh each poll
 * cycle rather than cached — polling is already infrequent (WorkManager
 * periodic interval), so the extra GET is cheap and avoids needing a new
 * persisted-state slot.
 */
class CommandRepository(
    private val api: SentinelXApi,
    private val commandDao: CommandRecordDao,
    private val secureStore: SecureStore,
    private val executor: CommandExecutor,
) {

    suspend fun reportCapabilities() {
        val token = secureStore.deviceToken ?: return
        runCatching {
            api.reportCapabilities(
                "Bearer $token",
                ReportCapabilitiesRequest(
                    agentType = AGENT_TYPE,
                    agentVersion = AGENT_VERSION,
                    capabilities = CommandExecutor.ACTION_RISK_LEVELS.map { (actionType, risk) ->
                        RecoveryCommandCapabilityDto(actionType = actionType, actionVersion = "1", localRiskLevel = risk)
                    },
                ),
            )
        }
    }

    suspend fun pollAndExecute() {
        val token = secureStore.deviceToken ?: return

        val command: RecoveryCommandDto = runCatching { api.getNextCommand("Bearer $token") }
            .getOrNull() ?: return

        val commandId = command.id

        if (commandDao.statusFor(commandId) == "completed") return

        if (CommandSigningVerifier.isExpired(command)) {
            reject(token, commandId, "Command already expired when received.")
            return
        }

        val publicKey = runCatching { api.getRecoveryPublicKey("Bearer $token").publicKey }.getOrNull() ?: return
        if (!CommandSigningVerifier.verify(command, publicKey)) {
            reject(token, commandId, "Signature verification failed.")
            return
        }

        if (command.actionType !in CommandExecutor.ACTION_RISK_LEVELS) {
            reject(token, commandId, "Action '${command.actionType}' is not supported by this agent build.")
            return
        }

        val alreadyReceived = commandDao.statusFor(commandId) != null
        val nonce = command.commandNonce
        if (!nonce.isNullOrEmpty() && !alreadyReceived && commandDao.nonceCount(nonce) > 0) {
            reject(token, commandId, "Nonce already processed (replay).")
            return
        }

        if (!alreadyReceived) {
            commandDao.insertIfAbsent(
                CommandRecord(
                    commandId = commandId,
                    nonce = nonce,
                    actionType = command.actionType,
                    status = "received",
                    receivedAtEpochMs = System.currentTimeMillis(),
                )
            )
        }

        runCatching { api.acknowledgeCommand("Bearer $token", commandId) }.getOrNull() ?: return
        commandDao.updateStatus(commandId, "acknowledged")

        runCatching { api.startCommand("Bearer $token", commandId) }.getOrNull() ?: return
        commandDao.updateStatus(commandId, "running")

        val result = runCatching { executor.execute(command.actionType, command.parametersJson) }
            .getOrElse { e -> ExecutionResult("failure", "Executor error: ${e.message}") }

        runCatching {
            api.completeCommand(
                "Bearer $token",
                commandId,
                CompleteCommandRequest(
                    resultCode = result.resultCode,
                    resultMessage = result.message,
                    resultData = result.data,
                    postActionSnapshot = result.data,
                ),
            )
        }.getOrNull() ?: return

        commandDao.markCompleted(commandId, System.currentTimeMillis())
    }

    private suspend fun reject(token: String, commandId: String, reason: String) {
        runCatching { api.rejectCommand("Bearer $token", commandId, RejectCommandRequest(reason = reason)) }
    }
}
