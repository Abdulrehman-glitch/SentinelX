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
    // Client-side idempotency key; the backend enforces UNIQUE(device, event_id).
    val eventId: String = "",
    // -1 = CPU could not be read; mapped to null on upload, never to 0%.
    val cpuPercent: Double,
    val memoryPercent: Double,
    val diskPercent: Double,
    val batterySummary: String,
    val attempts: Int = 0,
    // Structured mobile extras uploaded via /metrics/batch. -1 battery = unknown.
    val batteryPercent: Int = -1,
    val batteryCharging: Boolean = false,
    val networkTransport: String = "",
    val batteryTemperatureC: Double? = null,
    val thermalStatus: String = "",
    val networkValidated: Boolean? = null,
    val networkMetered: Boolean? = null,
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
