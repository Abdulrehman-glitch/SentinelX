package com.sentinelx.mobile.data.db

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query

/**
 * Local durability + replay-guard log for signed recovery commands. Mirrors
 * the desktop agent's SQLite command_log table (sentinelx_agent/store.py) —
 * every command's receipt is persisted before any network acknowledgement,
 * so a process death mid-command resumes from durable state instead of
 * re-executing or losing the result.
 */
@Entity(tableName = "command_log")
data class CommandRecord(
    @PrimaryKey val commandId: String,
    val nonce: String?,
    val actionType: String,
    val status: String,
    val receivedAtEpochMs: Long,
    val completedAtEpochMs: Long? = null,
)

@Dao
interface CommandRecordDao {

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertIfAbsent(record: CommandRecord)

    @Query("SELECT status FROM command_log WHERE commandId = :commandId")
    suspend fun statusFor(commandId: String): String?

    @Query("SELECT COUNT(*) FROM command_log WHERE nonce = :nonce")
    suspend fun nonceCount(nonce: String): Int

    @Query("UPDATE command_log SET status = :status WHERE commandId = :commandId")
    suspend fun updateStatus(commandId: String, status: String)

    @Query("UPDATE command_log SET status = 'completed', completedAtEpochMs = :completedAt WHERE commandId = :commandId")
    suspend fun markCompleted(commandId: String, completedAt: Long)
}
