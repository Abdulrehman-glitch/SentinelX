import Foundation

enum NetworkInterface: String, Codable, Sendable {
    case wifi
    case cellular
    case wiredEthernet = "wired_ethernet"
    case loopback
    case other
    case unavailable
}

/// Payload for `network.status` events. Interface-level status only — no
/// Wi-Fi scanning, SSIDs, or traffic inspection.
struct NetworkPayload: Codable, Sendable, Equatable {
    let reachable: Bool
    let interface: NetworkInterface
    let expensive: Bool
    let constrained: Bool
}
