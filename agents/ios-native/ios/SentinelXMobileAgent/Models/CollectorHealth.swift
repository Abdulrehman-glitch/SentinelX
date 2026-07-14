import Foundation

enum CollectorHealthState: String, Codable, Sendable {
    case healthy
    case degraded
    case disabled
    case permissionDenied = "permission_denied"
    case unsupported
    case failed
}

struct CollectorHealth: Codable, Sendable, Equatable, Identifiable {
    var id: String { collectorId }

    let collectorId: String
    let category: TelemetryCategory
    let enabled: Bool
    let health: CollectorHealthState
    let lastEventAt: Date?
    let errorMessage: String?

    enum CodingKeys: String, CodingKey {
        case collectorId = "collector_id"
        case category
        case enabled
        case health
        case lastEventAt = "last_event_at"
        case errorMessage = "error_message"
    }
}
