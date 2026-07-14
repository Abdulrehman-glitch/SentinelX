package com.sentinelx.mobile.data.db

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "queued_metrics")
data class QueuedMetric(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val capturedAtEpochMs: Long,
    val cpuPercent: Double,
    val memoryPercent: Double,
    val diskPercent: Double,
    val batterySummary: String,
    val attempts: Int = 0,
    // Structured mobile extras uploaded via /metrics/batch. -1 battery = unknown.
    val batteryPercent: Int = -1,
    val batteryCharging: Boolean = false,
    val networkTransport: String = "",
)

@Dao
interface QueuedMetricDao {

    @Insert
    suspend fun insert(metric: QueuedMetric): Long

    @Query("SELECT * FROM queued_metrics ORDER BY capturedAtEpochMs ASC LIMIT :limit")
    suspend fun oldestPending(limit: Int): List<QueuedMetric>

    @Query("DELETE FROM queued_metrics WHERE id = :id")
    suspend fun delete(id: Long)

    @Query("UPDATE queued_metrics SET attempts = attempts + 1 WHERE id = :id")
    suspend fun incrementAttempts(id: Long)

    @Query("DELETE FROM queued_metrics WHERE attempts >= :maxAttempts")
    suspend fun abandonExhausted(maxAttempts: Int): Int

    @Query(
        "DELETE FROM queued_metrics WHERE id NOT IN " +
            "(SELECT id FROM queued_metrics ORDER BY capturedAtEpochMs DESC LIMIT :keep)"
    )
    suspend fun trimToNewest(keep: Int): Int

    @Query("SELECT COUNT(*) FROM queued_metrics")
    fun countFlow(): Flow<Int>

    @Query("SELECT COUNT(*) FROM queued_metrics")
    suspend fun count(): Int

    @Query("DELETE FROM queued_metrics")
    suspend fun clearAll()
}
