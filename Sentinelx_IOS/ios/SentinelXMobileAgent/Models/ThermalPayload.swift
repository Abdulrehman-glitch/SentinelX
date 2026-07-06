import Foundation

enum ThermalState: String, Codable, Sendable {
    case nominal
    case fair
    case serious
    case critical
    case unknown
}

/// Payload for `thermal.state` events.
struct ThermalPayload: Codable, Sendable, Equatable {
    let state: ThermalState
}
