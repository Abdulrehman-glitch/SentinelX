import Foundation

struct QueueCounts: Equatable, Sendable {
    var pending = 0
    var inFlight = 0
    var failed = 0
    var oldestPendingAt: Date?
}

/// Durable offline queue (docs/spec/04 §25, 05 §30). Events are persisted
/// `pending` before any upload attempt; uploaders take FIFO batches
/// (→ `in_flight`), then either delete on acknowledgement or push back for
/// retry. `event_id` uniqueness gives duplicate protection end to end.
actor TelemetryQueue {
    static let pendingCap = 5000
    static let failedCap = 200
    static let maxAttempts = 8

    private let store: SQLiteTelemetryStore
    private let dateProvider: DateProviding
    private(set) var droppedByPrune = 0

    init(path: String, dateProvider: DateProviding = SystemDateProvider()) throws {
        self.store = try SQLiteTelemetryStore(path: path)
        self.dateProvider = dateProvider
    }

    /// Default on-device location: Application Support/sentinelx_queue.db.
    static func defaultPath() throws -> String {
        let directory = try FileManager.default.url(
            for: .applicationSupportDirectory, in: .userDomainMask,
            appropriateFor: nil, create: true
        )
        return directory.appendingPathComponent("sentinelx_queue.db").path
    }

    /// Persists an event as pending. Returns false for a duplicate event_id.
    @discardableResult
    func enqueue(_ event: TelemetryEvent) throws -> Bool {
        let now = ISO8601.string(from: dateProvider.now())
        let payload = try String(decoding: JSONCoding.encoder.encode(event.payload), as: UTF8.self)
        let metadata = try event.metadata.map {
            try String(decoding: JSONCoding.encoder.encode($0), as: UTF8.self)
        }
        let changes = try store.run("""
            INSERT OR IGNORE INTO telemetry_queue
            (event_id, device_id, category, type, source, sequence, payload_json,
             metadata_json, timestamp, status, retry_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)
            """, [
                .text(event.eventId.uuidString), .text(event.deviceId),
                .text(event.category.rawValue), .text(event.type), .text(event.source),
                event.sequence.map(SQLiteTelemetryStore.Value.int) ?? .null,
                .text(payload), metadata.map(SQLiteTelemetryStore.Value.text) ?? .null,
                .text(ISO8601.string(from: event.timestamp)), .text(now), .text(now),
            ])
        try pruneIfNeeded()
        return changes == 1
    }

    /// Oldest pending events, atomically marked in_flight.
    func nextBatch(limit: Int) throws -> [TelemetryEvent] {
        var events: [TelemetryEvent] = []
        try store.query("""
            SELECT event_id, device_id, category, type, source, sequence,
                   payload_json, metadata_json, timestamp
            FROM telemetry_queue WHERE status = 'pending' ORDER BY id ASC LIMIT ?
            """, [.int(limit)]) { statement in
            if let event = Self.decodeRow(statement) {
                events.append(event)
            }
        }
        if !events.isEmpty {
            try setStatus("in_flight", ids: events.map(\.eventId))
        }
        return events
    }

    /// Acknowledged events leave the queue for good.
    func markUploaded(_ ids: [UUID]) throws {
        guard !ids.isEmpty else { return }
        try store.run(
            "DELETE FROM telemetry_queue WHERE event_id IN (\(placeholders(ids.count)))",
            ids.map { .text($0.uuidString) }
        )
    }

    /// Transient failure: back to pending with the error recorded; events
    /// that exhausted maxAttempts become failed (kept for inspection).
    func markForRetry(_ ids: [UUID], error: String) throws {
        guard !ids.isEmpty else { return }
        let now = ISO8601.string(from: dateProvider.now())
        try store.run("""
            UPDATE telemetry_queue
            SET retry_count = retry_count + 1, last_error = ?, updated_at = ?,
                status = CASE WHEN retry_count + 1 >= ? THEN 'failed' ELSE 'pending' END
            WHERE event_id IN (\(placeholders(ids.count)))
            """, [.text(error), .text(now), .int(Self.maxAttempts)]
                + ids.map { .text($0.uuidString) })
    }

    /// Permanent rejection (server-side validation): never retried.
    func markFailed(_ ids: [UUID], error: String) throws {
        guard !ids.isEmpty else { return }
        let now = ISO8601.string(from: dateProvider.now())
        try store.run("""
            UPDATE telemetry_queue
            SET status = 'failed', last_error = ?, updated_at = ?
            WHERE event_id IN (\(placeholders(ids.count)))
            """, [.text(error), .text(now)] + ids.map { .text($0.uuidString) })
    }

    /// Recovery after relaunch or WS drop: unacknowledged sends go back to
    /// pending — the server's event_id idempotency makes re-sends safe.
    func requeueInFlight() throws {
        let now = ISO8601.string(from: dateProvider.now())
        try store.run(
            "UPDATE telemetry_queue SET status = 'pending', updated_at = ? WHERE status = 'in_flight'",
            [.text(now)]
        )
    }

    func clearFailed() throws {
        try store.run("DELETE FROM telemetry_queue WHERE status = 'failed'")
    }

    func counts() throws -> QueueCounts {
        var counts = QueueCounts()
        try store.query("""
            SELECT status, COUNT(*), MIN(CASE WHEN status = 'pending' THEN created_at END)
            FROM telemetry_queue GROUP BY status
            """) { statement in
            let count = SQLiteTelemetryStore.int(statement, 1) ?? 0
            switch SQLiteTelemetryStore.text(statement, 0) {
            case "pending":
                counts.pending = count
                counts.oldestPendingAt = SQLiteTelemetryStore.text(statement, 2)
                    .flatMap(ISO8601.date(from:))
            case "in_flight":
                counts.inFlight = count
            case "failed":
                counts.failed = count
            default:
                break
            }
        }
        return counts
    }

    // MARK: - Internals

    private func setStatus(_ status: String, ids: [UUID]) throws {
        let now = ISO8601.string(from: dateProvider.now())
        try store.run(
            "UPDATE telemetry_queue SET status = ?, updated_at = ? WHERE event_id IN (\(placeholders(ids.count)))",
            [.text(status), .text(now)] + ids.map { .text($0.uuidString) }
        )
    }

    private func pruneIfNeeded() throws {
        droppedByPrune += try prune(status: "pending", cap: Self.pendingCap)
        _ = try prune(status: "failed", cap: Self.failedCap)
    }

    private func prune(status: String, cap: Int) throws -> Int {
        try store.run("""
            DELETE FROM telemetry_queue WHERE status = ? AND id IN (
                SELECT id FROM telemetry_queue WHERE status = ?
                ORDER BY id DESC LIMIT -1 OFFSET ?
            )
            """, [.text(status), .text(status), .int(cap)])
    }

    private func placeholders(_ count: Int) -> String {
        Array(repeating: "?", count: count).joined(separator: ", ")
    }

    private static func decodeRow(_ statement: OpaquePointer) -> TelemetryEvent? {
        guard
            let idText = SQLiteTelemetryStore.text(statement, 0),
            let eventId = UUID(uuidString: idText),
            let deviceId = SQLiteTelemetryStore.text(statement, 1),
            let categoryText = SQLiteTelemetryStore.text(statement, 2),
            let category = TelemetryCategory(rawValue: categoryText),
            let type = SQLiteTelemetryStore.text(statement, 3),
            let source = SQLiteTelemetryStore.text(statement, 4),
            let payloadJSON = SQLiteTelemetryStore.text(statement, 6),
            let payload = try? JSONCoding.decoder.decode(JSONValue.self, from: Data(payloadJSON.utf8)),
            let timestampText = SQLiteTelemetryStore.text(statement, 8),
            let timestamp = ISO8601.date(from: timestampText)
        else {
            Log.telemetry.error("Dropping undecodable queue row")
            return nil
        }
        let metadata = SQLiteTelemetryStore.text(statement, 7).flatMap {
            try? JSONCoding.decoder.decode(TelemetryMetadata.self, from: Data($0.utf8))
        }
        return TelemetryEvent(
            eventId: eventId,
            deviceId: deviceId,
            timestamp: timestamp,
            category: category,
            type: type,
            source: source,
            sequence: SQLiteTelemetryStore.int(statement, 5),
            payload: payload,
            metadata: metadata
        )
    }
}
