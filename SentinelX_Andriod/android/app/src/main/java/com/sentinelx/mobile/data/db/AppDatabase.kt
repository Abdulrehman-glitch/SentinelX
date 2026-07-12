package com.sentinelx.mobile.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [QueuedMetric::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {

    abstract fun queuedMetricDao(): QueuedMetricDao

    companion object {
        fun build(context: Context): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, "sentinelx_agent.db")
                .fallbackToDestructiveMigration()
                .build()
    }
}
