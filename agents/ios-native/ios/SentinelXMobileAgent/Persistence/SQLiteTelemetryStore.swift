import Foundation
import SQLite3

/// Thin sqlite3 wrapper for the offline queue (docs/spec/05 §30). Not
/// thread-safe by itself — always confined inside the TelemetryQueue actor.
/// Adds `source`/`sequence` columns beyond the spec table: the envelope
/// (spec 05 §10) requires both to re-upload an event, so data-model
/// consistency wins over the narrower §30 field list (drift noted in
/// docs/STATUS.md).
final class SQLiteTelemetryStore {
    enum SQLiteError: Error, Equatable {
        case open(String)
        case prepare(String)
        case step(String)
    }

    private let db: OpaquePointer
    private static let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    private static let schema = """
    CREATE TABLE IF NOT EXISTS telemetry_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT UNIQUE NOT NULL,
        device_id TEXT NOT NULL,
        category TEXT NOT NULL,
        type TEXT NOT NULL,
        source TEXT NOT NULL,
        sequence INTEGER,
        payload_json TEXT NOT NULL,
        metadata_json TEXT,
        timestamp TEXT NOT NULL,
        status TEXT NOT NULL,
        retry_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_error TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_queue_status_id ON telemetry_queue (status, id);
    """

    init(path: String) throws {
        var handle: OpaquePointer?
        let flags = SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX
        guard sqlite3_open_v2(path, &handle, flags, nil) == SQLITE_OK, let handle else {
            let message = handle.map { String(cString: sqlite3_errmsg($0)) } ?? "unknown"
            if let handle { sqlite3_close(handle) }
            throw SQLiteError.open(message)
        }
        db = handle
        // exec, not step: the WAL pragma returns a result row.
        try run("PRAGMA journal_mode=WAL", multi: true)
        try run(Self.schema, multi: true)
    }

    deinit {
        sqlite3_close(db)
    }

    /// Bindable parameter values (String, Int, or nil).
    enum Value {
        case text(String)
        case int(Int)
        case null
    }

    @discardableResult
    func run(_ sql: String, _ bindings: [Value] = [], multi: Bool = false) throws -> Int {
        if multi {
            guard sqlite3_exec(db, sql, nil, nil, nil) == SQLITE_OK else {
                throw SQLiteError.step(String(cString: sqlite3_errmsg(db)))
            }
            return Int(sqlite3_changes(db))
        }
        let statement = try prepare(sql, bindings)
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw SQLiteError.step(String(cString: sqlite3_errmsg(db)))
        }
        return Int(sqlite3_changes(db))
    }

    /// Runs a SELECT; calls `row` with the stepped statement for each row.
    func query(_ sql: String, _ bindings: [Value] = [], row: (OpaquePointer) -> Void) throws {
        let statement = try prepare(sql, bindings)
        defer { sqlite3_finalize(statement) }
        while true {
            switch sqlite3_step(statement) {
            case SQLITE_ROW:
                row(statement)
            case SQLITE_DONE:
                return
            default:
                throw SQLiteError.step(String(cString: sqlite3_errmsg(db)))
            }
        }
    }

    static func text(_ statement: OpaquePointer, _ column: Int32) -> String? {
        sqlite3_column_text(statement, column).map { String(cString: $0) }
    }

    static func int(_ statement: OpaquePointer, _ column: Int32) -> Int? {
        sqlite3_column_type(statement, column) == SQLITE_NULL
            ? nil
            : Int(sqlite3_column_int64(statement, column))
    }

    private func prepare(_ sql: String, _ bindings: [Value]) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK, let statement else {
            throw SQLiteError.prepare(String(cString: sqlite3_errmsg(db)))
        }
        for (index, value) in bindings.enumerated() {
            let position = Int32(index + 1)
            switch value {
            case .text(let string):
                sqlite3_bind_text(statement, position, string, -1, Self.transient)
            case .int(let number):
                sqlite3_bind_int64(statement, position, Int64(number))
            case .null:
                sqlite3_bind_null(statement, position)
            }
        }
        return statement
    }
}
