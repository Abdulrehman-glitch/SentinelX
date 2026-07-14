package com.sentinelx.mobile.data.db

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

/**
 * Local activity timeline. Categories: monitoring, alerts, recovery,
 * connection, system, user. Severities: info, warning, critical.
 */
@Entity(tableName = "agent_events")
data class AgentEvent(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val atEpochMs: Long,
    val category: String,
    val severity: String,
    val title: String,
    val detail: String = "",
)

@Dao
interface AgentEventDao {

    @Insert
    suspend fun insert(event: AgentEvent): Long

    @Query("SELECT * FROM agent_events ORDER BY atEpochMs DESC LIMIT :limit")
    fun recentFlow(limit: Int): Flow<List<AgentEvent>>

    @Query("SELECT * FROM agent_events WHERE category = :category ORDER BY atEpochMs DESC LIMIT :limit")
    fun recentByCategoryFlow(category: String, limit: Int): Flow<List<AgentEvent>>

    @Query(
        "DELETE FROM agent_events WHERE id NOT IN " +
            "(SELECT id FROM agent_events ORDER BY atEpochMs DESC LIMIT :keep)"
    )
    suspend fun trimToNewest(keep: Int): Int

    @Query("DELETE FROM agent_events")
    suspend fun clearAll()
}
