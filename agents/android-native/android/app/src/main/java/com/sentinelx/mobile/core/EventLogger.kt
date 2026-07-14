package com.sentinelx.mobile.core

import com.sentinelx.mobile.data.db.AgentEvent
import com.sentinelx.mobile.data.db.AgentEventDao
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Fire-and-forget writer for the local activity timeline. */
class EventLogger(private val dao: AgentEventDao) {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    fun log(category: String, severity: String, title: String, detail: String = "") {
        scope.launch {
            dao.insert(
                AgentEvent(
                    atEpochMs = System.currentTimeMillis(),
                    category = category,
                    severity = severity,
                    title = title,
                    detail = detail,
                )
            )
            dao.trimToNewest(MAX_EVENTS)
        }
    }

    private companion object {
        const val MAX_EVENTS = 500
    }
}
