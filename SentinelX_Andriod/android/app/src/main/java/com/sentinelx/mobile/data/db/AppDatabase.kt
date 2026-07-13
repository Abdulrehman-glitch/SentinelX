package com.sentinelx.mobile.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(entities = [QueuedMetric::class, AgentEvent::class], version = 2, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {

    abstract fun queuedMetricDao(): QueuedMetricDao
    abstract fun agentEventDao(): AgentEventDao

    companion object {

        // v2: structured mobile fields on the queue + local activity timeline.
        // Hand-written so an upgrade install keeps any pending offline samples.
        private val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE queued_metrics ADD COLUMN batteryPercent INTEGER NOT NULL DEFAULT -1")
                db.execSQL("ALTER TABLE queued_metrics ADD COLUMN batteryCharging INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE queued_metrics ADD COLUMN networkTransport TEXT NOT NULL DEFAULT ''")
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS agent_events (" +
                        "id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                        "atEpochMs INTEGER NOT NULL, " +
                        "category TEXT NOT NULL, " +
                        "severity TEXT NOT NULL, " +
                        "title TEXT NOT NULL, " +
                        "detail TEXT NOT NULL)"
                )
            }
        }

        fun build(context: Context): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, "sentinelx_agent.db")
                .addMigrations(MIGRATION_1_2)
                .fallbackToDestructiveMigration()
                .build()
    }
}
