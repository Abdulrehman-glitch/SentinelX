import Foundation

enum BatteryState: String, Codable, Sendable {
    case unknown
    case unplugged
    case charging
    case full
}

/// Payload for `battery.snapshot` events. Emitted only when the level is
/// actually readable (0–100); iOS exposes no battery health or cycle count.
struct BatteryPayload: Codable, Sendable, Equatable {
    let level: Int
    let charging: Bool
    let state: BatteryState
    let lowPowerMode: Bool

    enum CodingKeys: String, CodingKey {
        case level
        case charging
        case state
        case lowPowerMode = "low_power_mode"
    }
}
