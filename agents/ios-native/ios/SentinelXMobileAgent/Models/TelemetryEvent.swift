import Foundation

/// Canonical telemetry envelope (docs/spec/05 §10). Immutable after
/// creation; `event_id` is the idempotency key across queue, REST and WS.
struct TelemetryEvent: Codable, Identifiable, Sendable, Equatable {
    var id: UUID { eventId }

    let eventId: UUID
    let deviceId: String
    let timestamp: Date
    let category: TelemetryCategory
    let type: String
    let source: String
    let sequence: Int?
    let payload: JSONValue
    let metadata: TelemetryMetadata?

    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case deviceId = "device_id"
        case timestamp
        case category
        case type
        case source
        case sequence
        case payload
        case metadata
    }

    /// TelemetryManager stamps the session sequence at acceptance time.
    func withSequence(_ sequence: Int) -> TelemetryEvent {
        TelemetryEvent(
            eventId: eventId,
            deviceId: deviceId,
            timestamp: timestamp,
            category: category,
            type: type,
            source: source,
            sequence: sequence,
            payload: payload,
            metadata: metadata
        )
    }
}

struct TelemetryMetadata: Codable, Sendable, Equatable {
    let platform: Platform
    let agentVersion: String
    let collectorVersion: String?
    let appBuild: String?
    let environment: String?

    enum CodingKeys: String, CodingKey {
        case platform
        case agentVersion = "agent_version"
        case collectorVersion = "collector_version"
        case appBuild = "app_build"
        case environment
    }
}
